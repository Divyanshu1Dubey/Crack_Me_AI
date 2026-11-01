"""Credit the retired 'dr-aarav-mehta' byline to the CrackCMS Editorial Team.

The byline (an MBBS, MD credential on about 100 seeded posts) could not be
verified as a real, consenting clinician, so the static blog and the seed
data now credit the editorial team (see RETIRED_AUTHOR_SLUGS in
frontend/src/content/authors.ts). seed_blogs skips rows that already exist,
so rows seeded before that change keep the old byline; published rows are
served by the public GET /api/blog/posts/.

Only the byline fields, and the one seeded title and description that named
the same credential, are rewritten, and only where they still hold the
retired values. No row is deleted or unpublished.
"""
from django.db import migrations
from django.db.models import Q

RETIRED_ID = "dr-aarav-mehta"
RETIRED_AUTHOR = "Dr. Aarav Mehta, MBBS, MD (Internal Medicine)"
EDITORIAL_ID = "crackcms-editorial"
EDITORIAL_AUTHOR = "CrackCMS Editorial Team"
EDITORIAL_ROLE = "Clinical Content Editors, CrackCMS"

# Seeded copy of upsc-cms-last-5-days-strategy, as the static post now reads.
RETITLED = (
    ("title",
     "UPSC CMS Last 5 Days: A Senior Internist’s Revision Plan",
     "UPSC CMS Last 5 Days: A Day-by-Day Revision Plan"),
    ("description",
     "A clinician’s day-by-day UPSC CMS revision plan for the final 5 days — "
     "high-yield triage, mock-test scoring, MCQ-solving patterns, sleep and exam-day "
     "checklist. Source-cited.",
     "A day-by-day UPSC CMS revision plan for the final 5 days — high-yield triage, "
     "mock-test scoring, MCQ-solving patterns, sleep and exam-day checklist. Source-cited."),
)


def credit_editorial_team(apps, schema_editor):
    BlogPost = apps.get_model("blog_engine", "BlogPost")
    BlogPost.objects.filter(Q(author_id=RETIRED_ID) | Q(author=RETIRED_AUTHOR)).update(
        author_id=EDITORIAL_ID, author=EDITORIAL_AUTHOR, author_role=EDITORIAL_ROLE)
    BlogPost.objects.filter(reviewed_by=RETIRED_ID).update(reviewed_by=EDITORIAL_ID)
    for field, old, new in RETITLED:
        BlogPost.objects.filter(**{field: old}).update(**{field: new})


class Migration(migrations.Migration):

    dependencies = [
        ("blog_engine", "0001_initial"),
    ]

    operations = [
        # Not reversible into the retired byline on purpose.
        migrations.RunPython(credit_editorial_team, migrations.RunPython.noop),
    ]
