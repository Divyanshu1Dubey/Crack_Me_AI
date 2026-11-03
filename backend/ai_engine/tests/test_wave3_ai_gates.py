"""Regression tests, wave 3 (group Z5-ai).

AI-08 /api/ai/screenshot/<id>/ applies the question bank's answer rule: the
     cited textbook page shows where (and often what) the answer is, so a
     user who may not see the answer gets 402 upgrade_required and nothing is
     rendered, stored or returned. A cache that is down (django_redis with
     IGNORE_EXCEPTIONS answers None) no longer reads as "already rendering";
     an unreadable textbook folder is a 404, not a 500; a stored render whose
     file is gone is rendered again.
AI   The ad-hoc explain-answer path is no cache oracle: a bank question with
     a blank option is still recognised (and paywalled), the ad-hoc path reads
     and writes its own cache namespace (batch jobs cache bank questions under
     question_id=None), and an exact duplicate cannot unlock a paywalled row.
AI   textbook-reference answers the exact stem of a paywalled bank question
     with 402 (its references are part of the explanation).
C12  Staff are never metered (the wallet's 'Unlimited' rule).
QE-03 Students read the AI explanation / mnemonic / references ahead of the
     curated fields, under the "Verified by Admin" badge: an admin's
     explain-question force_regenerate that changes a verified question's
     ai_explanation clears the mark (verification_cleared), and no other
     explain call stores AI text into a verified question. An admin
     regeneration that changes the stored text first takes a revision
     snapshot (the editor's undo restores text and mark), atomically with
     the save.
KB   kb_cleanup_legacy scans embeddings in keyset pages (no server-side
     cursor behind a transaction-mode pooler).

No test reaches an AI provider: clients are never built and AI calls are
patched.
"""
import hashlib
import json
import os
import shutil
import tempfile
from io import StringIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.db.models.query import QuerySet
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import TokenBalance
from accounts.models_freemium import FreeShowcaseQuestion
from ai_engine import offline
from ai_engine.services import AIService
from ai_engine.tests.test_wave2_answer_gate_and_fixes import OPTIONS, PNG, RICH, STEM, _Base

User = get_user_model()

GENERATED = {
    'ai_verified_answer': 'B', 'answer_mismatch': False, 'confidence_note': '',
    'why_correct': 'Generated for the ad-hoc question.',
    'why_wrong': {'A': 'No', 'C': 'No', 'D': 'No'},
    'core_concept': 'Ad-hoc concept', 'mnemonic': 'ADHOC',
}


def fake_render(pdf_path, page_num, output_dir, dpi=200):
    path = os.path.join(output_dir, f'book_page_{page_num + 1}.png')
    with open(path, 'wb') as fh:
        fh.write(PNG)
    return path


# ─── Page screenshots: entitlement ──────────────────────────────────────

class _ScreenshotBase(_Base):
    def setUp(self):
        super().setUp()
        self.media = tempfile.mkdtemp(prefix='w5-media-')
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=self.media)
        override.enable()
        self.addCleanup(override.disable)
        self.q.book_name = 'Harrison'
        self.q.page_number = '1234'
        self.q.save()

    def screenshot(self, user):
        from ai_engine.views import PageScreenshotView
        return self.call(PageScreenshotView, {}, user, method='get', question_id=self.q.id)

    def render_patches(self, find_pdf='/books/harrison.pdf'):
        from ai_engine.views import PageScreenshotView
        return (
            patch.object(PageScreenshotView, '_find_pdf', return_value=find_pdf),
            patch('ai_engine.document_processor.DocumentProcessor.extract_page_image',
                  side_effect=fake_render),
        )

    def store_file(self, name):
        path = os.path.join(self.media, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as fh:
            fh.write(PNG)
        self.q.page_screenshot.name = name
        self.q.save()


class PageScreenshotEntitlementTests(_ScreenshotBase):

    def test_free_user_gets_402_and_nothing_is_rendered_or_stored(self):
        from ai_engine.views import PageScreenshotView
        with patch.object(PageScreenshotView, '_render_and_store') as render:
            resp = self.screenshot(self.free)
        self.assert_paywalled(resp)
        self.assertNotIn('screenshot_url', resp.data)
        render.assert_not_called()
        self.q.refresh_from_db()
        self.assertFalse(self.q.page_screenshot)
        self.assertIsNone(cache.get(f'ai_page_screenshot_lock_v1:{self.q.id}'))
        self.assertIsNone(cache.get(f'ai_page_screenshot_miss_v1:{self.q.id}'))

    def test_free_user_never_gets_a_stored_screenshot_url(self):
        self.store_file('question_screenshots/stored.png')
        resp = self.screenshot(self.free)
        self.assert_paywalled(resp)
        self.assertNotIn('stored.png', json.dumps(resp.data))

    def test_showcase_question_is_free(self):
        FreeShowcaseQuestion.objects.create(question=self.q, year=2021, position=0)
        find, render = self.render_patches()
        with find, render:
            resp = self.screenshot(self.free)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('/media/question_screenshots/', resp.data['screenshot_url'])

    def test_scholarship_question_is_locked_even_when_showcased(self):
        self.q.is_scholarship_eligible = True
        self.q.save()
        FreeShowcaseQuestion.objects.create(question=self.q, year=2021, position=0)
        from ai_engine.views import PageScreenshotView
        with patch.object(PageScreenshotView, '_render_and_store') as render:
            self.assert_paywalled(self.screenshot(self.free))
        render.assert_not_called()

    def test_premium_and_admin_are_served(self):
        for user in (self.premium, self.admin):
            find, render = self.render_patches()
            with find, render:
                resp = self.screenshot(user)
            self.assertEqual(resp.status_code, 200, (user.username, resp.data))
            self.assertTrue(resp.data['screenshot_url'].endswith('.png'))


# ─── Page screenshots: robustness ───────────────────────────────────────

class PageScreenshotRobustnessTests(_ScreenshotBase):

    def test_cache_down_renders_instead_of_answering_rendering(self):
        """django_redis with IGNORE_EXCEPTIONS answers None from a failed
        cache.add; that is 'no lock available', not 'someone is rendering'."""
        down = MagicMock()
        down.get.return_value = None
        down.add.return_value = None
        find, render = self.render_patches()
        with patch('ai_engine.views.cache', down), find, render as extract:
            resp = self.screenshot(self.premium)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('screenshot_url', resp.data)
        self.assertEqual(extract.call_count, 1)
        down.delete.assert_not_called()  # no lock was taken, none is released

    def test_lock_held_elsewhere_is_still_202(self):
        cache.set(f'ai_page_screenshot_lock_v1:{self.q.id}', 1, 60)
        from ai_engine.views import PageScreenshotView
        with patch.object(PageScreenshotView, '_render_and_store') as render:
            resp = self.screenshot(self.premium)
        self.assertEqual(resp.status_code, 202)
        render.assert_not_called()
        self.assertEqual(cache.get(f'ai_page_screenshot_lock_v1:{self.q.id}'), 1,
                         "another request's lock is not released")

    def test_lock_is_released_after_a_render(self):
        find, render = self.render_patches()
        with find, render:
            self.assertEqual(self.screenshot(self.premium).status_code, 200)
        self.assertIsNone(cache.get(f'ai_page_screenshot_lock_v1:{self.q.id}'))

    def test_unreadable_textbook_folder_is_a_404_not_a_500(self):
        from ai_engine.views import PageScreenshotView
        with patch.object(PageScreenshotView, '_find_pdf', side_effect=PermissionError('denied')):
            resp = self.screenshot(self.premium)
        self.assertEqual(resp.status_code, 404)
        self.assertNotIn('screenshot_url', resp.data)
        self.assertNotIn('denied', json.dumps(resp.data))
        self.q.refresh_from_db()
        self.assertFalse(self.q.page_screenshot)

    def test_stored_render_is_served_while_its_file_exists(self):
        self.store_file('question_screenshots/here.png')
        find, render = self.render_patches()
        with find, render as extract:
            resp = self.screenshot(self.premium)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['screenshot_url'].endswith('/media/question_screenshots/here.png'))
        extract.assert_not_called()

    def test_stored_render_whose_file_is_gone_is_rendered_again(self):
        self.q.page_screenshot.name = 'question_screenshots/gone.png'
        self.q.save()
        find, render = self.render_patches()
        with find, render as extract:
            resp = self.screenshot(self.premium)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(extract.call_count, 1)
        self.assertNotIn('gone.png', resp.data['screenshot_url'])
        self.q.refresh_from_db()
        self.assertTrue(os.path.isfile(self.q.page_screenshot.path))

    def test_response_never_carries_a_filesystem_path(self):
        find, render = self.render_patches()
        with find, render:
            resp = self.screenshot(self.premium)
        body = json.dumps(resp.data)
        self.assertNotIn('screenshot_path', body)
        self.assertNotIn(os.path.basename(self.media), body)
        self.assertTrue(resp.data['screenshot_url'].startswith('http://testserver/media/'))


# ─── Ad-hoc explain-answer: no cache oracle ─────────────────────────────

class AdHocExplainOracleTests(_Base):
    BLANK_D = {'A': OPTIONS['A'], 'B': OPTIONS['B'], 'C': OPTIONS['C'], 'D': ''}

    def setUp(self):
        super().setUp()
        self.q.option_d = ''
        self.q.save()

    def batch_cache(self, question_text=STEM, options=None, key='C'):
        """What questions/tasks.py & co. write: explain_after_answer without
        question_id, i.e. the id=None namespace."""
        cache.set(AIService.explanation_cache_key(question_text, options or self.BLANK_D, key),
                  dict(RICH), 600)

    def test_bank_question_with_a_blank_option_is_paywalled_for_every_probe(self):
        self.batch_cache()
        with patch.object(AIService, 'explain_after_answer') as explain:
            for letter in 'ABCD':
                for options in (self.BLANK_D, {k: v for k, v in self.BLANK_D.items() if v}):
                    resp = self.explain_answer({
                        'question_text': STEM, 'options': options,
                        'correct_answer': letter, 'selected_answer': letter,
                    }, self.free)
                    self.assert_paywalled(resp)
                    self.assertNotIn(RICH['why_correct'], json.dumps(resp.data))
        explain.assert_not_called()
        self.assert_nothing_charged(self.free)

    def test_entitled_user_gets_the_bank_explanation_for_a_blank_option_match(self):
        self.store_rich()
        resp = self.explain_answer({'question_text': STEM, 'options': self.BLANK_D,
                                    'correct_answer': 'A', 'selected_answer': 'C'}, self.premium)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['why_correct'], RICH['why_correct'])
        self.assertTrue(resp.data['is_correct'], 'judged against the DB key, not the client key')

    def test_exact_match_miss_cannot_read_the_bank_cache(self):
        """A stored stem with stray whitespace defeats the exact match, but
        the cache key strips it: the ad-hoc path must not read that key."""
        type(self.q).objects.filter(pk=self.q.pk).update(question_text=STEM + '  ')
        self.batch_cache(question_text=STEM + '  ')
        with patch.object(AIService, 'explain_after_answer', return_value=dict(GENERATED)) as explain:
            resp = self.explain_answer({'question_text': STEM, 'options': self.BLANK_D,
                                        'correct_answer': 'C', 'selected_answer': 'C'}, self.free)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertNotIn(RICH['why_correct'], json.dumps(resp.data))
        self.assertEqual(resp.data['why_correct'], GENERATED['why_correct'])
        self.assertEqual(explain.call_args.kwargs['cache_scope'], AIService.ADHOC_CACHE_SCOPE)
        self.assertIsNone(explain.call_args.kwargs['question_id'])

    def test_ad_hoc_results_are_cached_in_their_own_namespace(self):
        text = 'An AI-generated question about digoxin?'
        opts = {'A': 'p', 'B': 'q', 'C': 'r', 'D': 's'}
        data = {'question_text': text, 'options': opts, 'correct_answer': 'B', 'selected_answer': 'A'}
        with patch.object(AIService, '_call_ai', return_value=json.dumps(GENERATED)) as call_ai:
            first = self.explain_answer(data, self.free)
            second = self.explain_answer(data, self.free)
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(call_ai.call_count, 1, 'the second call is a free cache hit')
        self.assertFalse(second.data['is_correct'])
        self.assertIsNone(AIService.get_cached_explanation(text, opts, 'B'),
                          'nothing lands in the bank namespace')
        self.assertIsNotNone(AIService.get_cached_explanation(
            text, opts, 'B', cache_scope=AIService.ADHOC_CACHE_SCOPE))

    def test_a_showcased_duplicate_does_not_unlock_a_paywalled_row(self):
        dup = type(self.q).objects.create(
            question_text=STEM, option_a=OPTIONS['A'], option_b=OPTIONS['B'],
            option_c=OPTIONS['C'], option_d='', correct_answer='C', year=2022,
            subject=self.q.subject, explanation='Curated duplicate.',
        )
        FreeShowcaseQuestion.objects.create(question=dup, year=2022, position=0)
        resp = self.explain_answer({'question_text': STEM, 'options': self.BLANK_D,
                                    'correct_answer': 'C', 'selected_answer': 'C'}, self.free)
        self.assert_paywalled(resp)

    def test_cache_key_without_a_scope_is_unchanged(self):
        legacy_payload = json.dumps({
            'id': None, 'q': STEM, 'o': {k: OPTIONS[k] for k in sorted(OPTIONS)}, 'a': 'C',
        }, sort_keys=True, ensure_ascii=False)
        legacy = 'ai_explain_v2_' + hashlib.sha256(legacy_payload.encode('utf-8')).hexdigest()
        self.assertEqual(AIService.explanation_cache_key(STEM, OPTIONS, 'C'), legacy)
        self.assertNotEqual(
            AIService.explanation_cache_key(STEM, OPTIONS, 'C', cache_scope=AIService.ADHOC_CACHE_SCOPE),
            legacy,
        )


# ─── Textbook references of a bank question ─────────────────────────────

class TextbookReferenceGateTests(_Base):
    REFS = [{'book': 'Harrison', 'page': 1234, 'excerpt': 'Digoxin toxicity: bidirectional VT.',
             'relevance_score': 0.9}]

    def references(self, user, text=STEM):
        from ai_engine.views import TextbookReferenceView
        return self.call(TextbookReferenceView, {'question_text': text}, user)

    def test_free_user_gets_402_for_a_paywalled_bank_stem(self):
        with patch.object(AIService, 'find_textbook_reference', return_value=self.REFS) as find:
            resp = self.references(self.free)
        self.assert_paywalled(resp)
        self.assertNotIn('Harrison', json.dumps(resp.data))
        find.assert_not_called()

    def test_scholarship_stem_is_locked_even_when_showcased(self):
        self.q.is_scholarship_eligible = True
        self.q.save()
        FreeShowcaseQuestion.objects.create(question=self.q, year=2021, position=0)
        with patch.object(AIService, 'find_textbook_reference', return_value=self.REFS):
            self.assert_paywalled(self.references(self.free))

    def test_showcase_stem_free_text_and_entitled_users_are_served(self):
        with patch.object(AIService, 'find_textbook_reference', return_value=self.REFS):
            self.assertEqual(self.references(self.premium).status_code, 200)
            self.assertEqual(self.references(self.admin).status_code, 200)
            free_text = self.references(self.free, text='digoxin toxicity arrhythmia')
            self.assertEqual(free_text.status_code, 200)
            self.assertEqual(free_text.data['references'][0]['book'], 'Harrison')
            FreeShowcaseQuestion.objects.create(question=self.q, year=2021, position=0)
            self.assertEqual(self.references(self.free).status_code, 200)


# ─── C12: staff are not metered ─────────────────────────────────────────

class StaffUnmeteredTests(_Base):
    def test_staff_ai_use_is_neither_metered_nor_capped(self):
        from ai_engine.views import _take_ai_tutor_slot, consume_ai_token, refund_ai_token
        staff = User.objects.create(username='w5-staff', role='student', is_staff=True)
        request = SimpleNamespace(user=staff)
        for _ in range(3):
            self.assertEqual(consume_ai_token(request, amount=10), (True, None))
        refund_ai_token(request, amount=10)
        self.assertFalse(TokenBalance.objects.filter(user=staff, total_tokens_used__gt=0).exists())
        self.assertEqual(_take_ai_tutor_slot(staff), (None, None))

    def test_students_are_still_metered(self):
        from ai_engine.views import consume_ai_token
        ok, err = consume_ai_token(SimpleNamespace(user=self.free), amount=1)
        self.assertTrue(ok)
        self.assertEqual(TokenBalance.objects.get(user=self.free).total_tokens_used, 1)


# ─── Offline PYQ lookup follows the bank's rule ─────────────────────────

class OfflinePyqEntitlementTests(_Base):
    PROBE = 'bidirectional ventricular tachycardia caused by which drug classically'

    def test_free_users_only_get_showcase_rows_staff_and_premium_get_the_bank(self):
        staff = User.objects.create(username='w5-staff-pyq', role='student', is_staff=True)
        self.assertIsNone(offline.find_similar_pyq(self.PROBE, user=self.free))
        self.assertIsNotNone(offline.find_similar_pyq(self.PROBE, user=self.premium))
        self.assertIsNotNone(offline.find_similar_pyq(self.PROBE, user=staff))
        FreeShowcaseQuestion.objects.create(question=self.q, year=2021, position=0)
        self.assertIsNotNone(offline.find_similar_pyq(self.PROBE, user=self.free))


# ─── QE-03: verified questions keep their reviewed explanation ──────────

class VerifiedExplanationTests(_Base):
    CURATED = 'Curated: digoxin causes bidirectional VT.'

    def setUp(self):
        super().setUp()
        self.verify()

    def verify(self):
        self.q.is_verified_by_admin = True
        self.q.verified_by = self.admin
        self.q.verified_at = timezone.now()
        self.q.save()

    def reload(self):
        self.q.refresh_from_db()
        return self.q

    def assert_still_verified(self):
        q = self.reload()
        self.assertTrue(q.is_verified_by_admin)
        self.assertEqual(q.verified_by_id, self.admin.id)
        self.assertIsNotNone(q.verified_at)

    def assert_mark_cleared(self):
        q = self.reload()
        self.assertFalse(q.is_verified_by_admin)
        self.assertIsNone(q.verified_by_id)
        self.assertIsNone(q.verified_at)

    def test_admin_regeneration_that_changes_the_text_clears_the_mark(self):
        shapes = {
            'analysis': {'analysis': 'Reviewed analysis', 'context': {}},
            'rich': dict(RICH),
            'empty': None,
        }
        for name, shape in shapes.items():
            with self.subTest(stored=name):
                self.q.ai_explanation = json.dumps(shape) if shape else ''
                self.q.save()
                self.verify()
                with patch.object(AIService, 'analyze_question', return_value='## Regenerated analysis'):
                    resp = self.explain_question({'force_regenerate': True}, self.admin)
                self.assertEqual(resp.status_code, 200, resp.data)
                self.assertTrue(resp.data['persisted'])
                self.assertTrue(resp.data['verification_cleared'])
                self.assert_mark_cleared()
                self.assertEqual(json.loads(self.q.ai_explanation)['analysis'], '## Regenerated analysis')

    def test_admin_regeneration_with_the_same_text_keeps_the_mark(self):
        same = {'analysis': '## Same analysis', 'context': {
            'subject': self.q.subject.name, 'topic': '', 'year': self.q.year,
            'exam_type': self.q.exam_type, 'exam_source': self.q.exam_source,
        }}
        self.q.ai_explanation = json.dumps(same, ensure_ascii=False)
        self.q.save()
        with patch.object(AIService, 'analyze_question', return_value='## Same analysis'):
            resp = self.explain_question({'force_regenerate': True}, self.admin)
        self.assertTrue(resp.data['persisted'])
        self.assertFalse(resp.data['verification_cleared'])
        self.assert_still_verified()

    def test_locked_explanation_is_neither_replaced_nor_unverified(self):
        self.q.lock_explanation = True
        self.q.save()
        with patch.object(AIService, 'analyze_question', return_value='## Regenerated analysis'):
            resp = self.explain_question({'force_regenerate': True}, self.admin)
        self.assertFalse(resp.data['persisted'])
        self.assertFalse(resp.data['verification_cleared'])
        self.assertEqual(self.reload().ai_explanation, '')
        self.assert_still_verified()

    def test_plain_explain_is_served_but_not_stored_into_a_verified_question(self):
        from questions.serializers import effective_explanation_for
        for user in (self.premium, self.admin):
            with self.subTest(user=user.username), \
                    patch.object(AIService, 'analyze_question', return_value='## Unreviewed analysis'):
                resp = self.explain_question({}, user)
                self.assertEqual(resp.status_code, 200, resp.data)
                self.assertEqual(resp.data['explanation'], '## Unreviewed analysis')
                self.assertFalse(resp.data['persisted'])
                self.assertFalse(resp.data['verification_cleared'])
        q = self.reload()
        self.assertEqual(q.ai_explanation, '')
        self.assert_still_verified()
        self.assertEqual(effective_explanation_for(q), self.CURATED)

    def test_student_regenerate_leaves_a_verified_question_alone(self):
        reviewed = json.dumps({'analysis': 'Reviewed analysis', 'context': {}})
        self.q.ai_explanation = reviewed
        self.q.save()
        with patch.object(AIService, 'analyze_question', return_value='## Student regenerate'):
            resp = self.explain_question({'force_regenerate': True}, self.premium)
        self.assertEqual(resp.data['explanation'], '## Student regenerate')
        self.assertFalse(resp.data['persisted'])
        self.assertFalse(resp.data['verification_cleared'])
        self.assertEqual(self.reload().ai_explanation, reviewed)
        self.assert_still_verified()

    def test_explain_answer_is_served_but_fills_nothing_on_a_verified_question(self):
        from questions.serializers import effective_explanation_for
        result = dict(RICH, ai_verified_answer='B', answer_mismatch=True,
                      clinical_pearl='Check potassium', exam_tip='Think digoxin',
                      around_concepts=['digoxin toxicity'])
        with patch.object(AIService, 'explain_after_answer', return_value=result) as explain:
            resp = self.explain_answer({'question_id': self.q.id, 'selected_answer': 'C'}, self.premium)
        self.assertEqual(resp.status_code, 200, resp.data)
        explain.assert_called_once()
        self.assertEqual(resp.data['why_correct'], RICH['why_correct'])
        q = self.reload()
        self.assertEqual(q.ai_explanation, '')
        self.assertEqual(q.ai_mnemonic, '')
        self.assertEqual(q.ai_clinical_pearl, '')
        self.assertEqual(q.learning_technique, '')
        self.assertFalse(q.ai_references)
        self.assertFalse(q.concept_keywords)
        self.assertFalse(q.is_disputed)
        self.assertFalse(q.needs_review)
        self.assert_still_verified()
        self.assertEqual(effective_explanation_for(q), self.CURATED)

    def test_unverified_questions_are_still_filled(self):
        self.q.is_verified_by_admin = False
        self.q.verified_by = None
        self.q.verified_at = None
        self.q.save()
        with patch.object(AIService, 'analyze_question', return_value='## First analysis'):
            resp = self.explain_question({}, self.premium)
        self.assertTrue(resp.data['persisted'])
        self.assertFalse(resp.data['verification_cleared'])
        self.assertEqual(json.loads(self.reload().ai_explanation)['analysis'], '## First analysis')

        self.q.ai_explanation = ''
        self.q.save()
        with patch.object(AIService, 'explain_after_answer', return_value=dict(RICH)):
            self.explain_answer({'question_id': self.q.id, 'selected_answer': 'C'}, self.premium)
        q = self.reload()
        self.assertEqual(json.loads(q.ai_explanation)['why_correct'], RICH['why_correct'])
        self.assertEqual(q.ai_mnemonic, RICH['mnemonic'])

    # Revision snapshot (undo), as generate-explanation / force-regenerate.

    REVIEWED = json.dumps({'analysis': 'Reviewed analysis', 'context': {}})

    def snapshots(self):
        from questions.models import QuestionRevisionSnapshot
        return QuestionRevisionSnapshot.objects.filter(question=self.q)

    def store_reviewed(self):
        self.q.ai_explanation = self.REVIEWED
        self.q.save()

    def test_admin_regeneration_snapshots_the_reviewed_text_for_undo(self):
        from rest_framework.test import force_authenticate
        from questions.views import QuestionViewSet
        self.store_reviewed()
        with patch.object(AIService, 'analyze_question', return_value='## Regenerated analysis'):
            resp = self.explain_question({'force_regenerate': True}, self.admin)
        self.assertTrue(resp.data['persisted'])
        self.assertTrue(resp.data['verification_cleared'])
        snap = self.snapshots().get()
        self.assertEqual(snap.reason, 'Before AI explain-question regenerate')
        self.assertEqual(snap.changed_by_id, self.admin.id)
        # Taken before the write: the reviewed text and the mark.
        self.assertEqual(snap.snapshot['ai_explanation'], self.REVIEWED)
        self.assertIs(snap.snapshot['is_verified_by_admin'], True)
        self.assertEqual(snap.snapshot['explanation'], self.CURATED)
        self.assert_mark_cleared()

        # The question editor's undo restores the reviewed text and the mark.
        request = self.factory.post('/api/questions/x/undo-last-revision/',
                                    {'revision_id': snap.id}, format='json')
        force_authenticate(request, user=self.admin)
        undo = QuestionViewSet.as_view({'post': 'undo_last_revision'})(request, pk=self.q.id)
        self.assertEqual(undo.status_code, 200, undo.data)
        q = self.reload()
        self.assertEqual(q.ai_explanation, self.REVIEWED)
        self.assertTrue(q.is_verified_by_admin)

    def test_admin_regeneration_of_an_unverified_question_is_undoable_too(self):
        self.q.is_verified_by_admin = False
        self.q.verified_by = None
        self.q.verified_at = None
        self.q.save()
        self.store_reviewed()
        with patch.object(AIService, 'analyze_question', return_value='## Regenerated analysis'):
            resp = self.explain_question({'force_regenerate': True}, self.admin)
        self.assertTrue(resp.data['persisted'])
        self.assertFalse(resp.data['verification_cleared'])
        snap = self.snapshots().get()
        self.assertEqual(snap.snapshot['ai_explanation'], self.REVIEWED)
        self.assertIs(snap.snapshot['is_verified_by_admin'], False)

    def test_no_snapshot_when_nothing_shared_changes(self):
        # Same text: nothing to undo.
        same = {'analysis': '## Same analysis', 'context': {
            'subject': self.q.subject.name, 'topic': '', 'year': self.q.year,
            'exam_type': self.q.exam_type, 'exam_source': self.q.exam_source,
        }}
        self.q.ai_explanation = json.dumps(same, ensure_ascii=False)
        self.q.save()
        with patch.object(AIService, 'analyze_question', return_value='## Same analysis'):
            self.assertTrue(self.explain_question({'force_regenerate': True}, self.admin).data['persisted'])
        # Answers that are served but not stored.
        with patch.object(AIService, 'analyze_question', return_value='## Other analysis'):
            for user, data in ((self.premium, {'force_regenerate': True}),
                               (self.admin, {'force_regenerate': True, 'prompt': 'Shorter, please'})):
                with self.subTest(user=user.username, data=data):
                    self.assertFalse(self.explain_question(data, user).data['persisted'])
        self.assertFalse(self.snapshots().exists())
        self.assert_still_verified()

        # A student's first fill of an unverified question stores without one.
        self.q.ai_explanation = ''
        self.q.is_verified_by_admin = False
        self.q.save()
        with patch.object(AIService, 'analyze_question', return_value='## First analysis'):
            self.assertTrue(self.explain_question({}, self.premium).data['persisted'])
        self.assertFalse(self.snapshots().exists())

    def test_a_failed_write_keeps_the_question_and_leaves_no_snapshot(self):
        from django.db.utils import OperationalError
        from questions.models import Question
        self.store_reviewed()
        with patch.object(AIService, 'analyze_question', return_value='## Regenerated analysis'), \
                patch.object(Question, 'save', side_effect=OperationalError('database is locked')):
            resp = self.explain_question({'force_regenerate': True}, self.admin)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['explanation'], '## Regenerated analysis')
        self.assertFalse(resp.data['persisted'])
        self.assertFalse(resp.data['verification_cleared'])
        # The snapshot was rolled back with the failed save.
        self.assertFalse(self.snapshots().exists())
        self.assertEqual(self.reload().ai_explanation, self.REVIEWED)
        self.assert_still_verified()


# ─── KB: keyset scan in kb_cleanup_legacy ───────────────────────────────

class KbCleanupKeysetTests(TestCase):
    TEXTS = (
        'Edema in nephrotic syndrome results from low plasma oncotic pressure.',
        'Digoxin toxicity classically causes bidirectional ventricular tachycardia.',
        'Hyperkalaemia is a marker of acute digoxin toxicity and worse outcome.',
    )

    def setUp(self):
        from django.utils import timezone
        from knowledge_base.models import KnowledgeChunk, KnowledgeEmbedding, KnowledgeSource
        from knowledge_base.services.embedding import EmbeddingService
        self.KnowledgeEmbedding = KnowledgeEmbedding
        source = KnowledgeSource.objects.create(slug='w5-notes', name='W5 notes',
                                                license='internal', attribution='CrackLabs Internal')
        hasher = EmbeddingService(model='bge-small-en-v1.5')
        self.hash_ids, self.real_ids = [], []
        for i, text in enumerate(self.TEXTS):
            chunk = KnowledgeChunk.objects.create(
                source=source, text=text, text_hash=f'w5-{i}', license='internal',
                attribution='CrackLabs Internal', approval_state=KnowledgeChunk.APPROVAL_AUTO,
                locator=f'notes/w5_{i}.md', approved_at=timezone.now(),
            )
            if i < 2:
                vec = hasher._hash_embed(text)
            else:
                vec = [((j * 37 + i) % 101) / 101.0 - 0.5 for j in range(384)]
            emb = KnowledgeEmbedding.objects.create(chunk=chunk, model='bge-small-en-v1.5',
                                                    dim=384, vector=vec)
            (self.hash_ids if i < 2 else self.real_ids).append(emb.id)

    def test_scan_pages_by_id_without_a_server_side_cursor(self):
        real_iterator = QuerySet.iterator
        model = self.KnowledgeEmbedding

        def guarded(qs, *args, **kwargs):
            if qs.model is model:
                raise AssertionError('KnowledgeEmbedding scanned with .iterator()')
            return real_iterator(qs, *args, **kwargs)

        out = StringIO()
        with patch('knowledge_base.management.commands.kb_cleanup_legacy.BATCH_SIZE', 1), \
                patch.object(QuerySet, 'iterator', guarded):
            call_command('kb_cleanup_legacy', '--apply', stdout=out)
        self.assertIn('2 hash embedding(s) deleted', out.getvalue())
        self.assertFalse(model.objects.filter(id__in=self.hash_ids).exists())
        self.assertEqual(list(model.objects.values_list('id', flat=True)), self.real_ids)

    def test_dry_run_counts_across_pages_and_deletes_nothing(self):
        out = StringIO()
        with patch('knowledge_base.management.commands.kb_cleanup_legacy.BATCH_SIZE', 2):
            call_command('kb_cleanup_legacy', stdout=out)
        self.assertIn('2 hash embedding(s) deleted', out.getvalue())
        self.assertEqual(self.KnowledgeEmbedding.objects.count(), 3)
