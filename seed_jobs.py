"""Jobs board seed script (no sample listings).

This script used to create three placeholder postings ("Medical Officer
(Coming Soon)", "Junior Resident (Non-Academic) - Coming Soon", "Senior
Medical Officer (NBE) - Coming Soon") that cited 2024/2025 vacancies and
claimed listings were being "scraped" / "indexed by our web crawler". None of
that was true, so it seeds nothing now: post real vacancies from the admin
(Admin -> Jobs), each with its official apply link.

    python seed_jobs.py                        # report leftover placeholder rows
    python seed_jobs.py --delete-placeholders  # delete them (admin-edited rows are kept)
"""
import os
import sys

import django

# Setup Django environment
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')
django.setup()

from jobs.models import Job  # noqa: E402

# Exact titles the old version of this script created.
PLACEHOLDER_TITLES = (
    "Medical Officer (Coming Soon)",
    "Junior Resident (Non-Academic) - Coming Soon",
    "Senior Medical Officer (NBE) - Coming Soon",
)


def seed_jobs(delete_placeholders: bool = False) -> None:
    print("No sample jobs are seeded; add real listings from the admin (Jobs).")
    leftovers = Job.objects.filter(title__in=PLACEHOLDER_TITLES, admin_edited=False)
    count = leftovers.count()
    if not count:
        return
    if delete_placeholders:
        leftovers.delete()
        print(f"Deleted {count} placeholder job(s) created by an earlier version of this script.")
    else:
        print(f"{count} placeholder job(s) from an earlier version of this script are still listed; "
              "re-run with --delete-placeholders to remove them.")


if __name__ == '__main__':
    seed_jobs(delete_placeholders='--delete-placeholders' in sys.argv[1:])
