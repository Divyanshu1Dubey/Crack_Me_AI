"""Questions hidden on 2026-11-07 (questions.content_repairs.apply_hides, migration 0046).

Only a duplicate or a wrong question is hidden (the owner's rule), only while it still holds the content it was
judged on, a duplicate only while its kept copy is active with the same key; a snapshot is stored first and
nothing is deleted.
"""
import re

from django.test import SimpleTestCase, TestCase

from questions import content_repairs as repairs
from questions.content_hashes import stem_hash
from questions.models import Question, QuestionRevisionSnapshot, Subject


def _apply(items):
    return repairs.apply_hides(items, question_model=Question, snapshot_model=QuestionRevisionSnapshot)


class ApplyHidesTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='Hides 2026-11-07', code='HID1107')

    def _question(self, text, key='B', active=True):
        return Question.objects.create(
            subject=self.subject, year=2018, question_text=text, option_a='Preference to control exposure B',
            option_b='Preference to control exposure A', option_c='c', option_d='d', correct_answer=key,
            is_active=active)

    def _item(self, q, keep=None):
        item = {'id': q.pk, 'stem_hash': stem_hash(q), 'reason': 'Hidden 2026-11-07: test'}
        if keep is not None:
            item['keep'] = keep.pk
        return item

    def test_a_duplicate_is_hidden_while_its_kept_copy_is_live_with_the_same_key(self):
        keep = self._question('The data regarding two exposures A and B is given below: Exposure A 5 Exposure B 10')
        copy = self._question('The data regarding two exposures A and B is given below: (2018 PYQ)')
        self.assertEqual(_apply([self._item(copy, keep)]), [(copy.pk, 'hidden')])
        copy.refresh_from_db()
        keep.refresh_from_db()
        self.assertFalse(copy.is_active)
        self.assertTrue(keep.is_active)
        snapshot = QuestionRevisionSnapshot.objects.get(question=copy)
        self.assertTrue(snapshot.snapshot['is_active'])
        self.assertEqual(snapshot.snapshot['question_text'], copy.question_text)
        self.assertIn('2026-11-07', snapshot.reason)
        self.assertTrue(Question.objects.filter(pk=copy.pk).exists())  # hidden, never deleted

    def test_a_duplicate_is_kept_when_its_twin_is_hidden_or_disagrees(self):
        keep = self._question('Twin question shown to students, stem one', active=False)
        copy = self._question('Copy question, stem two')
        self.assertEqual(_apply([self._item(copy, keep)]), [(copy.pk, 'kept copy not active')])
        keep.is_active = True
        keep.correct_answer = 'C'
        keep.save()
        self.assertEqual(_apply([self._item(copy, keep)]), [(copy.pk, 'kept copy has another key')])
        copy.refresh_from_db()
        self.assertTrue(copy.is_active)
        self.assertFalse(QuestionRevisionSnapshot.objects.exists())

    def test_an_edited_missing_or_already_hidden_question_is_left_alone(self):
        edited = self._question('A demo question with [image unavailable: x.png]')
        item = self._item(edited)
        Question.objects.filter(pk=edited.pk).update(question_text='An admin fixed this stem and added the figure')
        hidden = self._question('Already hidden question', active=False)
        results = dict(_apply([item, self._item(hidden), {'id': 999999, 'stem_hash': 'x' * 64, 'reason': 'r'}]))
        self.assertEqual(results, {edited.pk: 'stem or options changed', hidden.pk: 'already hidden',
                                   999999: 'missing'})
        self.assertTrue(Question.objects.get(pk=edited.pk).is_active)

    def test_a_second_run_changes_nothing(self):
        q = self._question('A question whose source omits the lab values it asks about')
        item = self._item(q)
        self.assertEqual(_apply([item]), [(q.pk, 'hidden')])
        self.assertEqual(_apply([item]), [(q.pk, 'already hidden')])
        self.assertEqual(QuestionRevisionSnapshot.objects.filter(question=q).count(), 1)


class HideListTests(SimpleTestCase):

    def test_the_approved_list_is_well_formed(self):
        ids = [item['id'] for item in repairs.HIDES_2026_11_07]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(sorted(ids), sorted([12605, 22456, 22631, 26454, 26451, 15370, 15618]))
        for item in repairs.HIDES_2026_11_07:
            self.assertRegex(item['stem_hash'], r'^[0-9a-f]{64}$')
            self.assertTrue(item['reason'].startswith('Hidden 2026-11-07: '))
            self.assertLessEqual(len(item['reason']), 200)
            self.assertNotIn(item.get('keep'), ids)  # a kept copy is never hidden by the same list
        self.assertEqual({item['id']: item.get('keep') for item in repairs.HIDES_2026_11_07 if item.get('keep')},
                         {12605: 12321, 22456: 6477, 22631: 2210})
        self.assertFalse(re.search(r'delete', repr(repairs.apply_hides.__code__.co_names)))
