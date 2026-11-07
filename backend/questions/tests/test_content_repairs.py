"""Content repairs of 2026-11-07 (questions.content_repairs, migration 0045).

The rows are seeded as crack_local holds them (the restored production data).
"""
import re

from django.test import TestCase

from questions import content_repairs as repairs
from questions.content_hashes import stem_hash
from questions.editorial import explanation_hash as editorial_explanation_hash
from questions.models import Question, QuestionRevisionSnapshot, Subject
from questions.serializers import effective_explanation_for
from questions.views import QuestionViewSet

FOUND = {
    2058: dict(
        question_text=(
            'A 36 year old man presents with decreased apetite, mouth soreness, diarrhoea and irritability. On '
            'examination he has a bright red tongue with a pigmented scaly rash around the neck. Which one of the '
            'following food items in his diet has a bearing on his disease?'),
        options=('Rice', 'Wheat', 'Corn', 'Fish'), correct_answer='C', lock_explanation=True, year=2025,
        explanation=(
            "The patient's symptoms (decreased appetite, mouth soreness, diarrhea, irritability, bright red tongue, "
            'and pigmented scaly rash around the neck) are classic for Pellagra, caused by niacin (Vitamin B3) '
            'deficiency. Wheat, especially when consumed as a staple without proper fortification or '
            'diversification, is associated with Pellagra, as it lacks sufficient niacin and tryptophan (a '
            'precursor to niacin).'),
    ),
    2065: dict(
        question_text=(
            'Which of the following joints are commonly affected in osteoarthritis?\nI. First metatarsophalangeal '
            'joint\nII. Proximal interphalangeal joint\nIII. Ankle joint\nIV. 5th and 6th cervical vertebrae joint\n'
            'Select the correct answer using the code given below:'),
        options=('I and II only', 'III and IV only', 'I, II and IV only', 'I, II, III and IV'),
        correct_answer='C', lock_explanation=True, year=2025,
        explanation=(
            'Osteoarthritis commonly affects weight-bearing and frequently used joints. The first '
            'metatarsophalangeal joint (I) and proximal interphalangeal joint (II) are frequently involved, while '
            'the ankle joint (III) is less commonly affected. The 5th and 6th cervical vertebrae joint (IV) is not '
            'typically associated with osteoarthritis.'),
    ),
    2103: dict(
        question_text='A radiopaque density may be noticed in poisoning by which of the following agents?',
        options=('Phenazopyridine', 'Ethylene glycol', 'Chloroquine', 'Chloral hydrate'),
        correct_answer='D', lock_explanation=True, year=2025,
        explanation=(
            'Ethylene glycol poisoning can cause radiopaque densities due to the formation of calcium oxalate '
            'crystals, which are visible on X-rays.'),
    ),
    2113: dict(
        question_text=(
            'Which of the following are included as a "Deficiency" under the Rashtriya Bal Swasthya Karyakram '
            '(RBSK)?\nI. Hypothyroidism\nII. Vitamin A deficiency\nIII. Anemia\nIV. Vitamin D deficiency\n'
            'Select the correct answer using the code given below:'),
        options=('I, II and III', 'I, II and IV', 'I, III and IV', 'II, III and IV'),
        correct_answer='D', lock_explanation=True, year=2025,
        explanation=(
            'Under RBSK, deficiencies include Hypothyroidism, Vitamin A deficiency, and Anemia. Vitamin D '
            'deficiency is not listed as a deficiency under RBSK.'),
    ),
    22462: dict(
        question_text=(
            'In a newborn, the Apgar score has been recorded at 1 minute of birth. The doctor recorded the '
            'following. observations:\n\nWhich one of the following best reflects the Apgar score of this newborn '
            'infant on a scale of 0 to 10? (2022 PYQ)'),
        options=('0', '2', '3', '5'), correct_answer='C', lock_explanation=False, year=2022,
        explanation=(
            'APGAR SCORE\n\nThe Apgar score is taken at 1 minute and again at 5 minutes after birth.\n\nIt requires '
            'immediate and careful observation of the heart rate, respiration, muscle tone, reflex response and '
            'colour of the infant.\n\nIt provides an immediate estimate of the physical condition of the baby.\n\n'
            'Reference: Park 26th edition; Preventive Medicine In Obstetrics, Paediatrics And Geriatrics'),
    ),
}
EXPLANATION_REWRITES = {2058, 2065, 2103, 2113}


def _apply():
    return repairs.apply_repairs(repairs.REPAIRS_2026_11_07, question_model=Question,
                                 snapshot_model=QuestionRevisionSnapshot)


class ContentRepairsTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='Repairs 2026-11-07', code='REP1107')

    def _seed(self, *ids):
        for pk in ids or FOUND:
            row = FOUND[pk]
            a, b, c, d = row['options']
            Question.objects.create(
                pk=pk, subject=self.subject, year=row['year'], question_text=row['question_text'],
                option_a=a, option_b=b, option_c=c, option_d=d, correct_answer=row['correct_answer'],
                explanation=row['explanation'], lock_explanation=row['lock_explanation'])

    def test_the_five_questions_are_repaired_without_changing_a_key(self):
        self._seed()
        stored_apgar_stem = Question.objects.get(pk=22462).question_text
        self.assertEqual(_apply(), [(pk, 'repaired') for pk in (2058, 2065, 2103, 2113, 22462)])
        for pk, row in FOUND.items():
            q = Question.objects.get(pk=pk)
            self.assertEqual(q.correct_answer, row['correct_answer'], pk)
            self.assertEqual(q.explanation_for_key, row['correct_answer'], pk)
            self.assertEqual(q.explanation_status, 'ai_generated', pk)
            self.assertEqual(q.explanation_stem_hash, stem_hash(q), pk)
            self.assertEqual(q.explanation_hash, editorial_explanation_hash(q), pk)
            self.assertEqual(q.lock_explanation, row['lock_explanation'], pk)
            # Students now read the repaired text.
            self.assertEqual(effective_explanation_for(q), q.explanation, pk)
            snapshot = QuestionRevisionSnapshot.objects.get(question=q)
            self.assertIsNone(snapshot.changed_by)
            self.assertIn('2026-11-07', snapshot.reason)
            self.assertEqual(snapshot.snapshot['explanation'], row['explanation'], pk)
            self.assertEqual(snapshot.snapshot['correct_answer'], row['correct_answer'], pk)

        for pk in EXPLANATION_REWRITES:
            q = Question.objects.get(pk=pk)
            self.assertEqual(q.explanation_origin, 'ai', pk)
            self.assertNotIn(FOUND[pk]['explanation'][:40], q.explanation, pk)
        self.assertIn('**maize (corn)**', Question.objects.get(pk=2058).explanation)
        self.assertIn('**ankle** are usually spared', Question.objects.get(pk=2065).explanation)
        self.assertIn('only **chloral hydrate** is on this list', Question.objects.get(pk=2103).explanation)
        self.assertIn('Congenital hypothyroidism is not in this group', Question.objects.get(pk=2113).explanation)

        apgar = Question.objects.get(pk=22462)
        self.assertEqual(apgar.explanation_origin, 'mixed')
        for line in ('Heart rate: 92 per minute', 'Respiratory effort: Slow, irregular', 'Muscle tone: Flaccid',
                     'Reflex response: No response', 'Colour: Body pink, extremities blue'):
            self.assertIn(line, apgar.question_text)
        self.assertNotIn('following. observations', apgar.question_text)
        self.assertTrue(apgar.explanation.startswith('**Scoring the observations**'))
        self.assertIn('Total = 1 + 1 + 0 + 0 + 1 = **3**', apgar.explanation)
        self.assertIn('Reference: Park 26th edition', apgar.explanation)  # the imported text is kept
        self.assertEqual(QuestionRevisionSnapshot.objects.get(question=apgar).snapshot['question_text'],
                         stored_apgar_stem)

    def test_a_second_run_changes_nothing(self):
        self._seed()
        _apply()
        after_first = {q.pk: (q.question_text, q.explanation) for q in Question.objects.all()}
        results = dict(_apply())
        self.assertEqual(results[22462], 'already repaired')
        for pk in EXPLANATION_REWRITES:
            self.assertEqual(results[pk], 'explanation edited', pk)
        self.assertEqual(QuestionRevisionSnapshot.objects.count(), 5)
        self.assertEqual({q.pk: (q.question_text, q.explanation) for q in Question.objects.all()}, after_first)

    def test_an_admin_edit_made_first_wins(self):
        self._seed(2058, 2065, 2103)
        Question.objects.filter(pk=2058).update(correct_answer='B')
        Question.objects.filter(pk=2065).update(admin_explanation_override='Reviewed text from an admin.')
        Question.objects.filter(pk=2103).update(explanation='An admin already rewrote this explanation.')
        results = dict(_apply())
        self.assertEqual(results[2058], 'key changed')
        self.assertEqual(results[2065], 'admin override')
        self.assertEqual(results[2103], 'explanation edited')
        self.assertEqual(results[2113], 'missing')
        self.assertFalse(QuestionRevisionSnapshot.objects.exists())
        self.assertEqual(Question.objects.get(pk=2058).explanation, FOUND[2058]['explanation'])
        self.assertEqual(Question.objects.get(pk=2058).explanation_status, 'none')

    def test_a_database_without_these_questions_is_left_alone(self):
        self.assertEqual({status for _, status in _apply()}, {'missing'})
        self.assertFalse(QuestionRevisionSnapshot.objects.exists())

    def test_snapshots_have_the_editor_revision_shape(self):
        self._seed(2058)
        q = Question.objects.get(pk=2058)
        self.assertEqual(set(QuestionViewSet()._serialize_revision_state(q)), set(repairs.REVISION_FIELDS))
        self.assertEqual(repairs.explanation_hash(q), editorial_explanation_hash(q))

    def test_every_answer_line_names_the_keyed_option(self):
        for repair in repairs.REPAIRS_2026_11_07:
            row = FOUND[repair['id']]
            letter = repair['key']
            option = row['options']['ABCD'.index(letter)]
            text = repair.get('set', {}).get('explanation') or repair.get('prepend', {}).get('explanation')
            match = re.search(r'\*\*Answer: \(([a-d])\) ([^*]+)\*\*', text)
            self.assertIsNotNone(match, repair['id'])
            self.assertEqual(match.group(1), letter.lower(), repair['id'])
            self.assertEqual(match.group(2).strip(), option, repair['id'])
            self.assertEqual(row['correct_answer'], letter, repair['id'])
