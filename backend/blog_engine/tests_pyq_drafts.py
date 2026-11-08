"""Blog drafts from the question bank (blog_engine/pyq_drafts.py): unpublished, no answers, created once."""
import io

from django.core.management import call_command
from django.test import TestCase

from blog_engine.models import BlogPost, GeneratedBlogDraft
from blog_engine.pyq_drafts import build_drafts, save_drafts
from questions.models import Question, Subject


class PyqDraftTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        gm = Subject.objects.create(name='General Medicine', code='GM-D')
        peds = Subject.objects.create(name='Paediatrics', code='PED-D')
        rows = []
        for n in range(1, 121):
            subject = gm if n <= 96 else peds
            topic = 'tuberculosis of the spine with a cold abscess' if n % 12 == 0 else f'condition number {n}'
            rows.append(Question(
                exam_type='cms', year=2019, paper=1, display_number=n, subject=subject, correct_answer='C',
                question_text=(f'A 40-year-old patient presents with symptoms suggesting {topic}, with weight loss, '
                               f'evening fever and a cough of three weeks; which investigation is most useful '
                               f'first in question {n} of this paper?'),
                option_a='Chest X-ray', option_b='Sputum CBNAAT', option_c='Mantoux test', option_d='CT scan'))
        Question.objects.bulk_create(rows)

    def test_a_paper_draft_and_a_topic_draft_without_answers(self):
        drafts = {d.slug: d for d in build_drafts()}
        paper = drafts['upsc-cms-2019-paper-i-analysis']
        self.assertIn('**120 questions**: General Medicine (96), Paediatrics (24)', paper.body)
        self.assertIn('| General Medicine | 96 | 1–96 |', paper.body)
        self.assertIn('120. A 40-year-old patient', paper.body)
        self.assertIn('official UPSC answer key', paper.body)
        topic = drafts['upsc-cms-pyqs-tuberculosis']
        self.assertIn('**10 questions**', topic.body)
        for draft in drafts.values():
            self.assertNotIn('Mantoux test', draft.body)  # options and answers stay in the question bank
            self.assertNotRegex(draft.body, r'(?i)answer: [ABCD]\b|correct answer is')

    def test_drafts_are_unpublished_created_once_and_never_overwrite_a_post(self):
        BlogPost.objects.create(slug='upsc-cms-pyqs-tuberculosis', title='An editor wrote this', description='d',
                                excerpt='e', category='Clinical Concepts', author='Editor', author_role='Editor',
                                date_published='2026-11-01', body='Written by hand.')
        out = io.StringIO()
        call_command('generate_pyq_blog_drafts', stdout=out)  # dry run
        self.assertIn('new paper draft 1', out.getvalue())
        self.assertFalse(GeneratedBlogDraft.objects.exists())
        call_command('generate_pyq_blog_drafts', apply=True, stdout=io.StringIO())
        post = BlogPost.objects.get(slug='upsc-cms-2019-paper-i-analysis')
        self.assertFalse(post.is_published)
        self.assertEqual(post.reviewed_by, '')
        self.assertIn('not reviewed', post.revision_log[0]['note'])
        self.assertEqual(BlogPost.objects.get(slug='upsc-cms-pyqs-tuberculosis').body, 'Written by hand.')
        post.delete()  # an editor deleted it: the next run does not create it again
        stats = save_drafts(build_drafts(), apply=True)
        self.assertFalse(BlogPost.objects.filter(slug='upsc-cms-2019-paper-i-analysis').exists())
        self.assertFalse([k for k in stats if k.startswith('new ')])  # nothing is created twice
        self.assertGreaterEqual(stats['already generated once'], 1)
