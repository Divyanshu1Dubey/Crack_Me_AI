"""Answer-key audit: classification rules, the DB-backed audit, the importers, the review-queue API.

Ground rules under test (docs/audit/MEDICAL_ACCURACY_DESIGN.md): nothing changes a key except an
explicit admin decision through ``questions.editorial.change_answer_key``; AI output is a review signal,
never evidence; one AI opinion is not enough for "likely correct"; "verified" needs strong evidence.
"""
import json
import tempfile
from datetime import timedelta
from io import StringIO
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from key_audit import classify as rules
from key_audit.importers import import_review_signals, import_source_keys
from key_audit.models import AuditResolution, QuestionAudit, ReviewClaim, SourceKey
from key_audit.reviews import AI_REVIEWER_LABEL
from key_audit.services import audit_question, audit_questions, on_question_changed
from questions.content_hashes import stem_hash
from questions.editorial import change_answer_key, unverify_question, verify_question
from questions.models import AnswerKeyChange, Question, QuestionFeedback, Subject

User = get_user_model()


def ai_review(best, *, verdict=None, key='A', confidence='high', ref='', issues=(), at=None, pass_no=1):
    return {
        'reviewer': AI_REVIEWER_LABEL, 'pass': pass_no, 'reviewer_ref': ref, 'verdict': verdict or (
            'agree' if best == key else 'disagree'),
        'best_option': best, 'confidence': confidence, 'explanation_check': '', 'issues': list(issues),
        'reason': 'test reason', 'quotes': [], 'stored_key': key, 'at': at or '2026-11-01T00:00:00+00:00',
        'source': 'test', 'stem_hash': '',
    }


def source_key(letter, *, confident=True, located=True, file='book.pdf'):
    return {'letter': letter, 'printed_letter': letter, 'confident': confident, 'located': located,
            'source_file': file, 'question_page': 3, 'question_number': 7, 'option_order': 'same',
            'method': 'answer_key_table'}


class ClassifyRuleTests(SimpleTestCase):
    """The status rules on plain data (key_audit.classify)."""

    def run_rules(self, **kw):
        kw.setdefault('key', 'A')
        return rules.classify(rules.AuditInput(**kw))

    def test_invalid_key_needs_review(self):
        r = self.run_rules(key='')
        self.assertEqual((r.status, r.reason), ('needs_review', 'invalid_or_missing_key'))

    def test_invalid_key_takes_the_printed_key_as_suggestion(self):
        r = self.run_rules(key='', signals=[rules.Signal('invalid_or_missing_key', 'empty')],
                           source_keys=[source_key('C')])
        self.assertEqual((r.status, r.reason, r.suggested_key, r.suggested_from),
                         ('needs_review', 'invalid_or_missing_key', 'C', 'source_key_mismatch'))

    def test_nothing_known_is_insufficient_evidence_not_likely_correct(self):
        r = self.run_rules()
        self.assertEqual((r.status, r.reason, r.priority), ('insufficient_evidence', 'no_evidence', 0.0))

    def test_one_ai_agreement_is_not_enough(self):
        r = self.run_rules(ai_reviews=[ai_review('A')])
        self.assertEqual((r.status, r.reason), ('insufficient_evidence', 'no_independent_agreement'))

    def test_printed_key_alone_is_not_enough(self):
        r = self.run_rules(source_keys=[source_key('A')])
        self.assertEqual(r.status, 'insufficient_evidence')

    def test_two_independent_agreements_are_likely_correct(self):
        r = self.run_rules(ai_reviews=[ai_review('A')], source_keys=[source_key('A')])
        self.assertEqual((r.status, r.reason), ('likely_correct', 'independent_agreement'))
        r = self.run_rules(ai_reviews=[ai_review('A', ref='r1', pass_no=2), ai_review('A', ref='r2', pass_no=2)])
        self.assertEqual(r.status, 'likely_correct')

    def test_ai_chosen_key_needs_a_non_ai_agreement(self):
        two_ai = [ai_review('A', ref='r1', pass_no=2), ai_review('A', ref='r2', pass_no=2)]
        self.assertEqual(self.run_rules(ai_reviews=two_ai, ai_chosen_key=True).status, 'insufficient_evidence')
        r = self.run_rules(ai_reviews=two_ai[:1], source_keys=[source_key('A')], ai_chosen_key=True)
        self.assertEqual(r.status, 'likely_correct')

    def test_ai_disagreement_opens_a_review_with_a_labelled_suggestion(self):
        r = self.run_rules(ai_reviews=[ai_review('C', confidence='medium')])
        self.assertEqual((r.status, r.reason, r.suggested_key, r.suggested_from),
                         ('needs_review', 'ai_review_disagrees', 'C', 'ai_review_disagrees'))
        self.assertEqual(r.priority, 55.0)

    def test_confident_source_key_mismatch_is_the_strongest_suggestion(self):
        r = self.run_rules(source_keys=[source_key('D')], ai_reviews=[ai_review('C')])
        self.assertEqual((r.status, r.reason, r.suggested_key), ('needs_review', 'source_key_mismatch', 'D'))
        self.assertEqual(r.priority, 95.5)   # strongest + 0.5 for the second open signal

    def test_unchecked_mismatch_loses_to_a_confident_match(self):
        r = self.run_rules(source_keys=[source_key('A'), source_key('C', confident=False, file='other.pdf')])
        self.assertNotIn('source_key_mismatch_unverified', [s['code'] for s in r.signals])
        r = self.run_rules(source_keys=[source_key('C', confident=False)])
        self.assertEqual(r.reason, 'source_key_mismatch_unverified')

    def test_confident_source_keys_that_disagree_are_contradictory(self):
        r = self.run_rules(source_keys=[source_key('B'), source_key('C', file='other.pdf')])
        self.assertEqual((r.status, r.reason), ('contradictory_sources', 'source_keys_disagree'))

    def test_official_key(self):
        official = {'reviewer': 'official_key', 'pass': 0, 'reviewer_ref': '', 'verdict': 'agree', 'best_option': 'A',
                    'stored_key': 'A', 'official_source': 'UPSC CMS 2023 key'}
        self.assertEqual(self.run_rules(official_reviews=[official]).status, 'verified')
        r = self.run_rules(official_reviews=[dict(official, best_option='B', verdict='disagree')])
        self.assertEqual((r.status, r.suggested_key), ('needs_review', 'B'))

    def test_human_decisions(self):
        at = timezone.now()
        strong = rules.HumanDecision('human:1', 'agree', 'A', True, at)
        weak = rules.HumanDecision('human:1', 'agree', 'A', False, at)
        old_signal = rules.Signal('open_wrong_answer_report', 'report', at=at - timedelta(days=1))
        self.assertEqual(self.run_rules(human=strong).status, 'verified')
        r = self.run_rules(human=weak, signals=[old_signal])
        self.assertEqual((r.status, r.reason), ('likely_correct', 'human_confirmed'))
        self.assertTrue(r.signals[0]['settled_by_review'])
        new_signal = rules.Signal('open_wrong_answer_report', 'report', at=at + timedelta(days=1))
        r = self.run_rules(human=strong, signals=[new_signal])
        self.assertEqual((r.status, r.reason), ('needs_review', 'new_signal_after_review'))
        r = self.run_rules(human=strong, signals=[rules.Signal('is_disputed', 'flag')])
        self.assertEqual(r.status, 'needs_review')
        r = self.run_rules(human=rules.HumanDecision('human:1', 'uncertain', '', False, at))
        self.assertEqual(r.reason, 'human_requested_review')
        r = self.run_rules(human=rules.HumanDecision('human:1', 'agree', 'B', True, at))
        self.assertEqual((r.reason, r.suggested_key), ('key_changed_after_review', 'B'))

    def test_explanation_conflict_after_a_decision_is_an_explanation_fix(self):
        at = timezone.now()
        r = self.run_rules(human=rules.HumanDecision('human:1', 'agree', 'A', False, at),
                           signals=[rules.Signal('explanation_states_other', 'names C', suggested_key='C')])
        self.assertEqual(r.status, 'likely_correct')
        self.assertIn('explanation_conflicts_with_reviewed_key', [s['code'] for s in r.signals])
        self.assertEqual(r.priority, 40.0)

    def test_image_missing(self):
        self.assertEqual(self.run_rules(image_missing=True).status, 'image_context_missing')
        r = self.run_rules(image_missing=True, source_keys=[source_key('B')])
        self.assertEqual(r.status, 'needs_review')

    def test_evidence(self):
        supported = {'status': 'supported', 'evidence_answer': 'A', 'citations': 2, 'tier_ok': True}
        self.assertEqual(self.run_rules(evidence=supported).reason, 'evidence_supported')
        r = self.run_rules(evidence=supported, ai_reviews=[ai_review('A')], source_keys=[source_key('A')])
        self.assertEqual((r.status, r.reason), ('verified', 'evidence_verified'))
        self.assertEqual(self.run_rules(evidence=dict(supported, tier_ok=False)).status, 'insufficient_evidence')
        r = self.run_rules(evidence={'status': 'conflict', 'evidence_answer': 'C'})
        self.assertEqual((r.reason, r.suggested_key), ('evidence_conflict', 'C'))

    def test_info_signals_do_not_open_a_review(self):
        r = self.run_rules(signals=[rules.Signal('needs_review_flag', 'flag')])
        self.assertEqual(r.status, 'insufficient_evidence')

    def test_ai_content_issues(self):
        r = self.run_rules(ai_reviews=[ai_review('A', issues=['garbled_text', 'options_incomplete'])])
        self.assertEqual(r.reason, 'ai_content_defect')
        self.assertEqual([s['code'] for s in r.signals].count('ai_content_defect'), 1)   # one per review
        r = self.run_rules(ai_reviews=[ai_review('A', issues=['wrong_subject'])])
        self.assertEqual(r.status, 'insufficient_evidence')


class _Fixture(TestCase):
    def setUp(self):
        self.subject = Subject.objects.create(name='Medicine', code='MED')
        self.admin = User.objects.create_superuser(username='audit_admin', email='admin@audit.test',
                                                   password='x-Unused-9f2!')

    def make(self, key='A', explanation='', exam='cms', year=2024, text='What is the first-line drug for anaphylaxis?',
             **kw):
        return Question.objects.create(
            subject=self.subject, question_text=text, option_a='Adrenaline', option_b='Hydrocortisone',
            option_c='Chlorpheniramine', option_d='Salbutamol', correct_answer=key, explanation=explanation,
            exam_type=exam, year=year, is_active=True, **kw)

    def add_source_key(self, question, letter, **kw):
        values = dict(question=question, source_file='Medicine pyqs.pdf', question_page=4, question_number=2,
                      printed_letter=letter, letter=letter, option_order='same', method='answer_key_table',
                      located=True, stem_hash=stem_hash(question), recovery_version='test',
                      recovered_at=timezone.now())
        values.update(kw)
        return SourceKey.objects.create(**values)


class AuditServiceTests(_Fixture):
    def test_dry_run_writes_nothing(self):
        q = self.make()
        prepared = audit_questions([q], save=False)
        self.assertEqual(prepared[0].fields['status'], 'insufficient_evidence')
        self.assertFalse(QuestionAudit.objects.exists())
        q.refresh_from_db()
        self.assertEqual(q.answer_key_status, 'unaudited')

    def test_save_writes_the_audit_mirrors_the_status_and_keeps_reviews(self):
        q = self.make()
        audit_questions([q], save=True, extra_reviews={q.pk: [ai_review('A')]})
        audit = QuestionAudit.objects.get(question=q)
        self.assertEqual(len(audit.reviews), 1)
        q.refresh_from_db()
        self.assertEqual(q.answer_key_status, audit.status)
        audit_questions([Question.objects.get(pk=q.pk)], save=True)   # a plain re-run keeps the reviews
        self.assertEqual(len(QuestionAudit.objects.get(question=q).reviews), 1)

    def test_explanation_naming_another_option(self):
        q = self.make(key='D', explanation='Option A is correct because adrenaline is the drug of choice.')
        audit = audit_question(q)
        self.assertEqual((audit.status, audit.status_reason, audit.suggested_key),
                         ('needs_review', 'explanation_states_other', 'A'))
        self.assertEqual(Question.objects.get(pk=q.pk).correct_answer, 'D')   # never changed

    def test_source_key_mismatch_and_stale_source_keys(self):
        q = self.make(key='A')
        self.add_source_key(q, 'C')
        audit = audit_question(q)
        self.assertEqual((audit.status_reason, audit.suggested_key), ('source_key_mismatch', 'C'))
        SourceKey.objects.update(stem_hash='0' * 64)   # recovered for other content
        audit = audit_question(q)
        self.assertEqual(audit.status, 'insufficient_evidence')
        self.assertEqual(audit.evidence_summary['stale_ignored']['source_keys'], 1)

    def test_skewed_key_distribution(self):
        rows = [Question(subject=self.subject, question_text=f'Question number {i} about drugs?', option_a='a',
                         option_b='b', option_c='c', option_d='d', correct_answer='A' if i < 45 else 'B',
                         exam_type='neet_pg', year=2025, is_active=True) for i in range(55)]
        Question.objects.bulk_create(rows)
        keyed_a = Question.objects.filter(exam_type='neet_pg', correct_answer='A').first()
        keyed_b = Question.objects.filter(exam_type='neet_pg', correct_answer='B').first()
        self.assertEqual(audit_question(keyed_a).status_reason, 'skewed_key_distribution')
        self.assertEqual(audit_question(keyed_b).status, 'insufficient_evidence')
        self.add_source_key(keyed_a, 'A')   # the printed key answers the default-key suspicion
        self.assertNotEqual(audit_question(keyed_a).status_reason, 'skewed_key_distribution')

    def test_key_change_by_an_admin_is_a_human_decision(self):
        q = self.make(key='D')
        with self.captureOnCommitCallbacks(execute=True):
            change_answer_key(q, 'A', actor=self.admin, reason='Adrenaline is first line in anaphylaxis.',
                              evidence=[{'kind': 'note', 'text': 'clinical guideline'}])
        audit = QuestionAudit.objects.get(question=q)
        self.assertEqual((audit.status, audit.status_reason, audit.key_provenance, audit.original_key),
                         ('likely_correct', 'human_confirmed', 'admin', 'D'))
        q2 = self.make(key='D', text='Another question about anaphylaxis treatment?')
        with self.captureOnCommitCallbacks(execute=True):
            change_answer_key(q2, 'A', actor=self.admin, reason='Official key says A for this item.',
                              evidence=[{'kind': 'official_key', 'source_title': 'UPSC CMS 2024 key'}])
        self.assertEqual(QuestionAudit.objects.get(question=q2).status, 'verified')
        self.assertEqual(Question.objects.get(pk=q2.pk).answer_key_status, 'verified')

    def test_stem_change_voids_earlier_decisions(self):
        q = self.make(key='D')
        with self.captureOnCommitCallbacks(execute=True):
            change_answer_key(q, 'A', actor=self.admin, reason='Official key says A for this item.',
                              evidence=[{'kind': 'official_key', 'source_title': 'UPSC CMS 2024 key'}])
        old_hash = stem_hash(q)
        q.refresh_from_db()
        q.question_text = 'What is the first-line drug for septic shock?'
        q.save()
        on_question_changed(q, old_key='A', old_stem_hash=old_hash, reason='stem edited')
        audit = QuestionAudit.objects.get(question=q)
        self.assertIsNotNone(audit.content_changed_at)
        self.assertEqual(audit.status, 'insufficient_evidence')

    def test_report_after_a_decision_reopens_the_review(self):
        q = self.make(key='A')
        verify_question(q, actor=self.admin)
        self.assertEqual(QuestionAudit.objects.get(question=q).status, 'likely_correct')
        student = User.objects.create_user(username='student1', email='s@audit.test', password='x-Unused-9f2!')
        QuestionFeedback.objects.create(question=q, user=student, category='wrong_answer', comment='key is wrong')
        self.assertEqual(audit_question(q).status_reason, 'new_signal_after_review')

    def test_unverify_sends_the_question_back_to_review(self):
        q = self.make(key='A')
        verify_question(q, actor=self.admin)
        unverify_question(q, actor=self.admin, reason='The option text looks garbled now.')
        audit = QuestionAudit.objects.get(question=q)
        self.assertEqual((audit.status, audit.status_reason), ('needs_review', 'human_requested_review'))

    def test_change_answer_key_rejects_non_explanation_fields(self):
        from django.core.exceptions import ValidationError
        q = self.make(key='D')
        with self.assertRaises(ValidationError):
            change_answer_key(q, 'A', actor=self.admin, reason='Adrenaline is first line in anaphylaxis.',
                              explanation_fields={'answer_key_status': 'verified', 'explanation': 'x'})
        q.refresh_from_db()
        self.assertEqual((q.correct_answer, q.answer_key_status), ('D', 'unaudited'))


class ImporterTests(_Fixture):
    def write(self, rows):
        handle = tempfile.NamedTemporaryFile('w', suffix='.jsonl', delete=False, encoding='utf-8')
        with handle:
            for row in rows:
                handle.write((row if isinstance(row, str) else json.dumps(row)) + '\n')
        self.addCleanup(Path(handle.name).unlink)
        return handle.name

    def line(self, q, **kw):
        row = {'question_id': q.pk, 'stem_hash': stem_hash(q), 'source_file': r'C:\local\dir\Medicine pyqs.pdf',
               'question_page': 4, 'question_number': 2, 'answer_page': 6, 'printed_letter': 'C', 'letter': 'C',
               'option_order': 'same', 'method': 'answer_key_table', 'located': True,
               'recovery_version': 'v2', 'recovered_at': '2026-11-03T10:00:00+00:00'}
        row.update(kw)
        return row

    def test_source_keys_dry_run_then_apply_then_idempotent(self):
        q = self.make(key='A')
        other = self.make(key='B', text='A second, unrelated question about asthma?')
        path = self.write([
            self.line(q),
            self.line(other, stem_hash='f' * 64),                       # made for other content
            {k: v for k, v in self.line(other).items() if k != 'stem_hash'},   # no hash
            {'question_id': q.pk, 'status': 'no_source_key'},
            {'question_id': 999999, 'stem_hash': 'a' * 64},
            'not json',
        ])
        report = import_source_keys(path)
        self.assertEqual((report.valid, report.created), (1, 1))
        self.assertEqual(report.skipped['content_changed'], 1)
        self.assertEqual(report.skipped['no_stem_hash'], 1)
        self.assertEqual(report.skipped['no_source_key'], 1)
        self.assertEqual(report.skipped['unknown_question'], 1)
        self.assertEqual(report.skipped['not_json'], 1)
        self.assertFalse(SourceKey.objects.exists())                    # dry run
        import_source_keys(path, apply=True)
        row = SourceKey.objects.get()
        self.assertEqual(row.source_file, 'Medicine pyqs.pdf')          # no local directory stored
        self.assertTrue(row.confident)
        self.assertEqual(import_source_keys(path, apply=True).unchanged, 1)
        self.assertEqual(SourceKey.objects.count(), 1)
        self.assertEqual(Question.objects.get(pk=q.pk).correct_answer, 'A')   # never changed

    def test_prototype_field_names_and_assume_current_content(self):
        q = self.make(key='A')
        proto = {'question_id': q.pk, 'source_file': 'Anaesthesia pyqs.pdf', 'source_page': 35, 'qno': 2,
                 'evidence_page': 36, 'source_letter': 'D', 'bank_letter': 'D', 'option_order': 'assumed_same',
                 'method': 'answer_key_table', 'located': True, 'status': 'mismatch',
                 'chapter': 'Anesthesia NEET 2020', 'chapter_parsed': {'exam': 'neet_pg', 'year': 2020}}
        path = self.write([proto])
        self.assertEqual(import_source_keys(path).skipped['no_stem_hash'], 1)
        report = import_source_keys(path, apply=True, assume_current_content=True)
        self.assertEqual(report.created, 1)
        row = SourceKey.objects.get()
        self.assertEqual((row.question_page, row.question_number, row.answer_page, row.source_year),
                         (35, 2, 36, 2020))
        self.assertFalse(row.confident)   # option order not checked

    def test_command_defaults_to_dry_run(self):
        q = self.make(key='A')
        path = self.write([self.line(q)])
        out = StringIO()
        call_command('import_source_keys', path, stdout=out)
        self.assertIn('Dry run', out.getvalue())
        self.assertFalse(SourceKey.objects.exists())
        call_command('import_source_keys', path, '--apply', stdout=StringIO())
        self.assertEqual(QuestionAudit.objects.get(question=q).status_reason, 'source_key_mismatch')

    def test_review_signals(self):
        q = self.make(key='A')
        review = {'question_id': q.pk, 'stem_hash': stem_hash(q), 'pass': 1, 'reviewer': AI_REVIEWER_LABEL,
                  'verdict': 'disagree', 'best_option': 'B', 'confidence': 'high', 'issues': [], 'reason': 'r',
                  'stored_key': 'A'}
        human = dict(review, reviewer='human:5')
        path = self.write([review, human])
        report, _ = import_review_signals(path)
        self.assertEqual(report.valid, 1)
        self.assertTrue(any(k.startswith('bad_review') for k in report.skipped))
        self.assertFalse(QuestionAudit.objects.exists())
        import_review_signals(path, apply=True)
        audit = QuestionAudit.objects.get(question=q)
        self.assertEqual((audit.status_reason, audit.suggested_key), ('ai_review_disagrees', 'B'))
        first_at = audit.reviews[0]['at']
        import_review_signals(path, apply=True)   # same file again: same review, first time kept
        audit.refresh_from_db()
        self.assertEqual((len(audit.reviews), audit.reviews[0]['at']), (1, first_at))
        self.assertEqual(Question.objects.get(pk=q.pk).correct_answer, 'A')

    def test_audit_command_dry_run_and_apply(self):
        q = self.make(key='')
        out = StringIO()
        call_command('audit_answer_keys', '--json', stdout=out)
        data = json.loads(out.getvalue())
        self.assertEqual((data['mode'], data['status']), ('dry-run', {'needs_review': 1}))
        self.assertFalse(QuestionAudit.objects.exists())
        call_command('audit_answer_keys', '--apply', stdout=StringIO())
        self.assertEqual(QuestionAudit.objects.get(question=q).status_reason, 'invalid_or_missing_key')


class ReviewQueueApiTests(_Fixture):
    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.q = self.make(key='D', explanation='Option A is correct because adrenaline is the drug of choice.')
        self.calm = self.make(key='A', text='Which vitamin deficiency causes scurvy?')
        audit_questions([self.q, self.calm], save=True)

    def url(self, name, qid=None):
        return reverse(f'key_audit:{name}', kwargs={'question_id': qid} if qid else None)

    def test_permissions(self):
        student = User.objects.create_user(username='student2', email='st@audit.test', password='x-Unused-9f2!')
        for client, expected in ((APIClient(), (401, 403)), (self._client(student), (403,))):
            for name, qid in (('queue-list', None), ('queue-summary', None), ('queue-detail', self.q.pk)):
                self.assertIn(client.get(self.url(name, qid)).status_code, expected)
            res = client.post(self.url('queue-resolve', self.q.pk), {'resolution': 'key_confirmed',
                                                                    'reason': 'looks right to me'}, format='json')
            self.assertIn(res.status_code, expected)
        self.assertEqual(Question.objects.get(pk=self.q.pk).correct_answer, 'D')

    def _client(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def test_list_summary_detail(self):
        res = self.client.get(self.url('queue-list'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['results'][0]['question_id'], self.q.pk)   # highest priority first
        res = self.client.get(self.url('queue-list'), {'status': 'needs_review', 'has_suggestion': 'true'})
        self.assertEqual([r['question_id'] for r in res.data['results']], [self.q.pk])
        summary = self.client.get(self.url('queue-summary')).data
        self.assertEqual(summary['total'], 2)
        self.assertEqual(summary['open_signals'].get('explanation_states_other'), 1)
        detail = self.client.get(self.url('queue-detail', self.q.pk)).data
        self.assertEqual(detail['question']['correct_answer'], 'D')
        self.assertEqual(detail['suggested_key'], 'A')

    def test_ai_reviews_are_labelled_as_review_signals(self):
        audit_questions([Question.objects.get(pk=self.calm.pk)], save=True,
                        extra_reviews={self.calm.pk: [ai_review('A')]})
        detail = self.client.get(self.url('queue-detail', self.calm.pk)).data
        self.assertEqual(detail['reviews'][0]['kind'], 'ai')
        self.assertIn('not evidence', detail['reviews'][0]['label'])

    def test_claims(self):
        other = User.objects.create_user(username='admin2', email='a2@audit.test', password='x-Unused-9f2!',
                                         role='admin')
        self.assertEqual(self.client.post(self.url('queue-claim', self.q.pk)).status_code, 200)
        other_client = self._client(other)
        self.assertEqual(other_client.post(self.url('queue-claim', self.q.pk)).status_code, 409)
        res = other_client.post(self.url('queue-resolve', self.q.pk),
                                {'resolution': 'key_confirmed', 'reason': 'confirmed by the second admin'},
                                format='json')
        self.assertEqual(res.status_code, 409)
        listed = other_client.get(self.url('queue-list'), {'unclaimed': 'true'}).data['results']
        self.assertNotIn(self.q.pk, [r['question_id'] for r in listed])      # hidden from the other reviewer
        listed = self.client.get(self.url('queue-list'), {'unclaimed': 'true'}).data['results']
        self.assertIn(self.q.pk, [r['question_id'] for r in listed])         # still listed for its claimant
        ReviewClaim.objects.update(expires_at=timezone.now() - timedelta(minutes=1))
        self.assertEqual(other_client.post(self.url('queue-claim', self.q.pk)).status_code, 200)

    def test_claim_insert_race_returns_the_existing_claim(self):
        from unittest import mock
        now = timezone.now()
        ReviewClaim.objects.create(question=self.q, claimed_by=self.admin, claimed_at=now,
                                   expires_at=now + timedelta(minutes=10))
        real = ReviewClaim.objects.select_for_update
        calls = {'n': 0}

        def first_lookup_misses(*args, **kwargs):
            calls['n'] += 1
            qs = real(*args, **kwargs)
            return qs.none() if calls['n'] == 1 else qs   # a concurrent request inserted the row meanwhile

        with mock.patch.object(ReviewClaim.objects, 'select_for_update', side_effect=first_lookup_misses):
            res = self.client.post(self.url('queue-claim', self.q.pk))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(ReviewClaim.objects.filter(question=self.q).count(), 1)

    def test_resolve_key_change_without_strong_evidence_is_likely_correct(self):
        res = self.client.post(self.url('queue-resolve', self.q.pk), {
            'resolution': 'key_changed', 'new_key': 'A', 'expected_key': 'D',
            'reason': 'The explanation and the pharmacology agree on adrenaline.',
            'evidence': [{'kind': 'note', 'text': 'standard management'}],
        }, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual((res.data['current_key'], res.data['audit_status']), ('A', 'likely_correct'))
        change = AnswerKeyChange.objects.get(question=self.q)
        self.assertEqual((change.old_key, change.new_key, change.source, change.audit_status_before),
                         ('D', 'A', 'review_queue', 'needs_review'))
        self.assertTrue(AuditResolution.objects.filter(question=self.q, key_change=change).exists())
        from accounts.models import AdminAuditLog
        self.assertTrue(AdminAuditLog.objects.filter(action='audit_resolution', resource_id=str(self.q.pk)).exists())

    def test_resolve_with_official_key_evidence_is_verified(self):
        res = self.client.post(self.url('queue-resolve', self.calm.pk), {
            'resolution': 'key_confirmed', 'reason': 'Matches the official answer key.',
            'evidence': [{'kind': 'official_key', 'source_title': 'UPSC CMS 2024 Paper I official key, Q12'}],
        }, format='json')
        self.assertEqual(res.data['audit_status'], 'verified')

    def test_resolve_rejects_stale_view_bad_evidence_and_mass_assignment(self):
        url = self.url('queue-resolve', self.q.pk)
        res = self.client.post(url, {'resolution': 'key_confirmed', 'expected_key': 'B',
                                     'reason': 'confirming what I saw on screen'}, format='json')
        self.assertEqual((res.status_code, res.data['code']), (409, 'key_changed'))
        for evidence in ([{'kind': 'ai_said_so'}], [{'kind': 'passage', 'source_title': 'Book', 'page_label': '12'}],
                         [{'kind': 'guideline_url', 'source_title': 'WHO', 'url': 'javascript:alert(1)'}]):
            res = self.client.post(url, {'resolution': 'key_confirmed', 'reason': 'confirming with evidence',
                                         'evidence': evidence}, format='json')
            self.assertEqual(res.status_code, 400, evidence)
        stranger = self.add_source_key(self.calm, 'A')
        res = self.client.post(url, {'resolution': 'key_confirmed', 'reason': 'confirming with a source key',
                                     'evidence': [{'kind': 'source_key', 'source_key_id': stranger.pk}]}, format='json')
        self.assertEqual(res.status_code, 400)
        res = self.client.post(url, {'resolution': 'key_changed', 'new_key': 'A', 'reason': 'with extra fields',
                                     'explanation_fields': {'is_active': 'false'}}, format='json')
        self.assertEqual(res.status_code, 400)
        q = Question.objects.get(pk=self.q.pk)
        self.assertEqual((q.correct_answer, q.is_active), ('D', True))
        self.assertFalse(AuditResolution.objects.exists())

    def test_confirming_an_invalid_key_is_refused(self):
        bad = self.make(key='', text='A question that lost its key in the import?')
        audit_questions([bad], save=True)
        res = self.client.post(self.url('queue-resolve', bad.pk), {'resolution': 'key_confirmed',
                                                                   'reason': 'cannot confirm nothing'}, format='json')
        self.assertEqual(res.status_code, 400)

    def test_deferred_and_dropped(self):
        res = self.client.post(self.url('queue-resolve', self.calm.pk), {'resolution': 'deferred',
                                                                         'reason': 'need the source paper first'},
                               format='json')
        self.assertEqual(res.data['audit_reason'], 'human_requested_review')
        self.client.post(self.url('queue-resolve', self.q.pk), {'resolution': 'dropped',
                                                                'reason': 'two options are correct here'},
                         format='json')
        self.assertTrue(Question.objects.get(pk=self.q.pk).is_dropped)
        listed = self.client.get(self.url('queue-list')).data['results']
        self.assertNotIn(self.q.pk, [r['question_id'] for r in listed])


class BatchSourceKeyApiTests(_Fixture):
    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.url = reverse('key_audit:queue-accept-source-keys')
        self.q1 = self.make(key='A')
        self.q2 = self.make(key='A', text='Which isolation precaution is used for MRSA carriers?')
        self.q3 = self.make(key='A', text='Which vitamin deficiency causes phrynoderma in children?')
        self.k1 = self.add_source_key(self.q1, 'C')
        self.k2 = self.add_source_key(self.q2, 'B', option_order='assumed_same')   # not confident
        self.k3 = self.add_source_key(self.q3, 'D')
        audit_questions([self.q1, self.q2, self.q3], save=True)

    def test_accepts_only_checked_confident_items_one_decision_each(self):
        self.q3.question_text = 'Which vitamin deficiency causes phrynoderma in adults?'   # edited since recovery
        self.q3.save()
        res = self.client.post(self.url, {'reason': 'Printed answer tables checked page by page.', 'items': [
            {'question_id': self.q1.pk, 'expected_key': 'A', 'source_key_id': self.k1.pk},
            {'question_id': self.q2.pk, 'expected_key': 'A', 'source_key_id': self.k2.pk},
            {'question_id': self.q3.pk, 'expected_key': 'A', 'source_key_id': self.k3.pk},
            {'question_id': self.q1.pk, 'expected_key': 'A', 'source_key_id': self.k1.pk},
        ]}, format='json')
        self.assertEqual(res.status_code, 200)
        by_id = {r['question_id']: r for r in res.data['results'][:3]}
        self.assertEqual((by_id[self.q1.pk]['ok'], by_id[self.q1.pk]['new_key']), (True, 'C'))
        self.assertEqual(by_id[self.q1.pk]['audit_status'], 'likely_correct')   # tier 4: not "verified"
        self.assertEqual(by_id[self.q2.pk]['error'], 'not_a_confident_source_key')
        self.assertEqual(by_id[self.q3.pk]['error'], 'source_key_for_other_content')
        self.assertEqual(res.data['results'][3]['error'], 'bad_or_duplicate_item')
        self.assertEqual(res.data['accepted'], 1)
        change = AnswerKeyChange.objects.get(question=self.q1)
        self.assertEqual((change.old_key, change.new_key, change.evidence[0]['kind']), ('A', 'C', 'source_key'))
        self.assertEqual(Question.objects.get(pk=self.q2.pk).correct_answer, 'A')

    def test_refuses_a_changed_key_a_claim_and_bad_requests(self):
        other = User.objects.create_user(username='admin3', email='a3@audit.test', password='x-Unused-9f2!',
                                         role='admin')
        ReviewClaim.objects.create(question=self.q1, claimed_by=other, claimed_at=timezone.now(),
                                   expires_at=timezone.now() + timedelta(minutes=10))
        res = self.client.post(self.url, {'reason': 'Printed answer tables checked page by page.', 'items': [
            {'question_id': self.q1.pk, 'expected_key': 'A', 'source_key_id': self.k1.pk},
            {'question_id': self.q3.pk, 'expected_key': 'B', 'source_key_id': self.k3.pk},
        ]}, format='json')
        errors = [r['error'] for r in res.data['results']]
        self.assertEqual(errors, ['claimed', 'key_changed'])
        self.assertEqual(self.client.post(self.url, {'reason': 'short', 'items': []}, format='json').status_code, 400)
        many = [{'question_id': i, 'expected_key': 'A', 'source_key_id': 1} for i in range(26)]
        self.assertEqual(self.client.post(self.url, {'reason': 'Printed answer tables checked.', 'items': many},
                                          format='json').status_code, 400)
        student = User.objects.create_user(username='student9', email='s9@audit.test', password='x-Unused-9f2!')
        client = APIClient()
        client.force_authenticate(student)
        self.assertEqual(client.post(self.url, {'reason': 'Printed answer tables checked.', 'items': []},
                                     format='json').status_code, 403)
        self.assertFalse(AnswerKeyChange.objects.exists())
