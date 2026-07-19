import os
import sys
import django

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')
django.setup()

from questions.models import ExamTrack, Subject, Topic, Question, Announcement
from jobs.models import Job
from accounts.models import CustomUser

def run():
    print("Creating Default Exam Tracks...")
    # UPSC CMS
    cms, _ = ExamTrack.objects.get_or_create(
        code="cms",
        defaults={
            "name": "UPSC CMS",
            "conducting_body": "UPSC",
            "vacancies": "1,358 vacancies (854 Cat-I, 494 Cat-II)",
            "exam_pattern_summary": "CBT 2x250 marks + 100-mark Personality Test",
            "source_url": "https://upsc.gov.in"
        }
    )

    # NEET PG
    neet_pg, _ = ExamTrack.objects.get_or_create(
        code="neet_pg",
        defaults={
            "name": "NEET PG",
            "conducting_body": "NBEMS",
            "exam_pattern_summary": "CBT, 180 MCQs, 3h30m, +4/-1 marking",
            "source_url": "https://natboard.edu.in"
        }
    )

    # INI-CET
    inicet, _ = ExamTrack.objects.get_or_create(
        code="ini_cet",
        defaults={
            "name": "INI-CET",
            "conducting_body": "AIIMS/JIPMER/PGIMER",
            "exam_pattern_summary": "~200 MCQs, 3h, CBT",
            "source_url": "https://aiimsexams.ac.in"
        }
    )

    # FMGE
    fmge, _ = ExamTrack.objects.get_or_create(
        code="fmge",
        defaults={
            "name": "FMGE",
            "conducting_body": "NBEMS",
            "exam_pattern_summary": "300 MCQs, two 2.5h shifts, no negative marking",
            "source_url": "https://natboard.edu.in"
        }
    )

    # USMLE
    usmle, _ = ExamTrack.objects.get_or_create(
        code="usmle",
        defaults={
            "name": "USMLE",
            "conducting_body": "NBME/FSMB",
        }
    )

    track_map = {
        'cms': cms,
        'neet_pg': neet_pg,
        'usmle': usmle,
        'fmge': fmge,
        'ini_cet': inicet,
    }

    # 1. Update CustomUsers
    print("Migrating CustomUsers...")
    for user in CustomUser.objects.all():
        if user.target_exam == 'UPSC CMS':
            user.active_exam_track = cms
        elif user.target_exam == 'NEET PG':
            user.active_exam_track = neet_pg
        elif user.target_exam == 'USMLE':
            user.active_exam_track = usmle
        elif user.target_exam == 'FMGE':
            user.active_exam_track = fmge
        elif user.target_exam == 'INI-CET':
            user.active_exam_track = inicet
        else:
            user.active_exam_track = cms # default
        user.save(update_fields=['active_exam_track'])

    # 2. Update Questions, Subjects, Topics
    print("Migrating Subjects...")
    for sub in Subject.objects.all():
        if sub.exam_type in track_map:
            sub.exam_track = track_map[sub.exam_type]
            sub.save(update_fields=['exam_track'])
    
    print("Migrating Topics...")
    for top in Topic.objects.all():
        if top.subject and top.subject.exam_track:
            top.exam_track = top.subject.exam_track
            top.save(update_fields=['exam_track'])

    print("Migrating Questions...")
    for q in Question.objects.all():
        if q.exam_type in track_map:
            q.exam_track = track_map[q.exam_type]
            q.save(update_fields=['exam_track'])

    # 3. Update Jobs
    print("Migrating Jobs...")
    for job in Job.objects.all():
        tags = job.exam_track_tags
        for tag in tags:
            tag_clean = tag.lower().strip()
            if tag_clean in track_map:
                job.exam_tracks.add(track_map[tag_clean])

    # 4. Update Announcements
    print("Migrating Announcements...")
    for ann in Announcement.objects.all():
        if ann.target_exam_track in track_map:
            ann.exam_tracks.add(track_map[ann.target_exam_track])
        elif ann.target_exam_track == 'all':
            ann.exam_tracks.add(cms, neet_pg, usmle, fmge, inicet)

    print("Data migration complete!")

if __name__ == '__main__':
    run()
