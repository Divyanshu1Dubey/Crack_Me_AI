"""Views for serving UPSC CMS resources and documents."""
import os
from pathlib import Path
from django.conf import settings
from django.http import FileResponse, Http404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions


MEDURA_DIR = os.path.join(settings.BASE_DIR, 'Medura_Train')


def _candidate_filenames(filename: str):
    """Yield likely filename variants present across environments."""
    normalized = filename.strip()
    if not normalized:
        return

    yield normalized

    if normalized.startswith('Copy of '):
        yield normalized[len('Copy of '):]
    else:
        yield f'Copy of {normalized}'


def _resolve_resource_path(filename: str):
    """Resolve a resource file path with fallback variants for deployment drift."""
    for candidate in _candidate_filenames(filename):
        filepath = os.path.join(MEDURA_DIR, candidate)
        if os.path.exists(filepath):
            return filepath

    # Last-resort fallback: match by UUID suffix when prefixes differ.
    stem = Path(filename).stem
    uuid_suffix = stem.split('_')[-1] if '_' in stem else ''
    if uuid_suffix:
        for entry in os.listdir(MEDURA_DIR):
            if entry.lower().endswith('.pdf') and uuid_suffix in Path(entry).stem:
                filepath = os.path.join(MEDURA_DIR, entry)
                if os.path.exists(filepath):
                    return filepath

    return None

# Map of resource categories to their files
RESOURCE_CATALOG = {
    'official_documents': {
        'title': 'Official UPSC Documents',
        'items': [
            {'id': 'cms_notice', 'name': 'UPSC CMS Official Notice', 'filename': 'Copy of UPSC CMS NOTICE_cf899a6a-fcee-4f8d-90f9-921be87452f1.pdf', 'category': 'notice'},
            {'id': 'form_notice', 'name': 'UPSC Application Form Notice', 'filename': 'Copy of UPSC FORM NOTICE_8344318f-6970-45aa-bab2-cc45560810c3.pdf', 'category': 'notice'},
            {'id': 'daf', 'name': 'CMS Detailed Application Form (DAF)', 'filename': 'CMS-DAF-10 sept_005d379e-5849-4c5d-b0db-12e3297c915a.pdf', 'category': 'application'},
            {'id': 'timetable', 'name': 'UPSC CMS Exam Timetable', 'filename': 'Copy of UPSC CMS Time table_d17c2330-91f7-4112-9f2a-ad69b5081f1b.pdf', 'category': 'schedule'},
        ]
    },
    'exam_resources': {
        'title': 'Exam Syllabus & Prerequisites',
        'items': [
            {'id': 'syllabus', 'name': 'Complete CMS Exam Syllabus', 'filename': 'Copy of Exam syllabus_e88dc081-8787-4c6f-af13-e88841e1a1b2.pdf', 'category': 'syllabus'},
            {'id': 'prerequisites', 'name': 'Prerequisites for Written Exam', 'filename': 'Copy of PREREQUISTIE FOR WRITTEN EXAMINATION_9f6a26a7-0de4-458a-ac2d-438fb4191552.pdf', 'category': 'eligibility'},
        ]
    },
    'certificates': {
        'title': 'Certificate Formats & Proformas',
        'items': [
            {'id': 'obc_cert', 'name': 'OBC Certificate Format', 'filename': 'Copy of Performa for OBC_1c21253a-640a-41b9-b4f8-8d59d8552d8a.pdf', 'category': 'certificate'},
            {'id': 'obc_instructions', 'name': 'OBC Creamy Layer Instructions', 'filename': 'Copy of Instructions for OBC Certificate creamy layer_1d86f27c-055b-40ac-b46a-97b3810cbb6c.pdf', 'category': 'certificate'},
            {'id': 'obc_declaration', 'name': 'OBC Self-Declaration Proforma', 'filename': 'Copy of Proforma by declaration of obc_4a31da70-8edc-49b8-ad7e-3cd7e55cc614.pdf', 'category': 'certificate'},
            {'id': 'sc_st_cert', 'name': 'SC/ST Certificate Format', 'filename': 'Copy of Performa for SC-ST_837607e9-33fc-4a36-a265-4309a517f3a4.pdf', 'category': 'certificate'},
            {'id': 'ews_cert', 'name': 'EWS Certificate Format', 'filename': 'Copy of Proforma FOR EWS_4dcab7dc-aee3-437a-9ab8-014c92954cc8.pdf', 'category': 'certificate'},
            {'id': 'disability_cert', 'name': 'Disability Certificate Format', 'filename': 'Copy of Disability certificate_a6dd1656-2e4a-4637-9b6c-3f9f0c633b6b.pdf', 'category': 'certificate'},
            {'id': 'name_affidavit', 'name': 'Affidavit for Name Change', 'filename': 'AFFIDAVIT FOR NAME_4a1179a9-15c8-4290-a31e-245d28502174.pdf', 'category': 'certificate'},
        ]
    },
    'experience_travel': {
        'title': 'Experience & Travel Forms',
        'items': [
            {'id': 'experience', 'name': 'Experience Claiming Proforma', 'filename': 'Copy of Performa for claiming experience_1d085b38-ea64-4634-b3e1-f038a8eb743e.pdf', 'category': 'form'},
            {'id': 'armed_forces', 'name': 'Armed Forces Personnel Benefits Form', 'filename': 'Copy of Proforma for claiming Serving-Retired Armed Force Personnel Benefits_511237e9-02a3-4d60-9102-16852024a4c4.pdf', 'category': 'form'},
            {'id': 'ta_rules', 'name': 'Travel Allowance Rules', 'filename': 'Copy of TRAVELLING ALLOWANCES_2e447db6-6b61-47fb-b430-1bf4d729d9c7.pdf', 'category': 'form'},
            {'id': 'ta_form', 'name': 'Travel Allowance Claim Form', 'filename': 'Copy of Travelling allowances form_1c7ec776-7e05-4329-90bd-3be53755911f.pdf', 'category': 'form'},
        ]
    },
}


class ResourceCatalogView(APIView):
    """List all available UPSC CMS resources and documents."""
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response(RESOURCE_CATALOG)


class ResourceDownloadView(APIView):
    """Download a specific resource PDF by ID."""
    permission_classes = [permissions.AllowAny]

    def get(self, request, resource_id):
        # Find the resource in catalog
        for category in RESOURCE_CATALOG.values():
            for item in category['items']:
                if item['id'] == resource_id:
                    filepath = _resolve_resource_path(item['filename'])
                    if filepath:
                        return FileResponse(
                            open(filepath, 'rb'),
                            content_type='application/pdf',
                            as_attachment=False,
                            filename=f"{item['name']}.pdf"
                        )
                    raise Http404(f"File not found on server for resource '{resource_id}'")
        raise Http404('Resource not found')


class ExamGuideView(APIView):
    """Return comprehensive UPSC CMS exam guide data."""
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        guide = {
            'exam_name': 'UPSC Combined Medical Services (CMS) Examination',
            'conducting_body': 'Union Public Service Commission (UPSC)',
            'frequency': 'Once a year',
            'mode': 'Computer-Based Examination (CBE)',
            'total_marks': 600,
            'eligibility': {
                'qualification': 'MBBS degree from a recognized institution (final year students can apply provisionally)',
                'age_limit': {
                    'general': '32 years (as of August 1st of exam year)',
                    'obc': '35 years (3 years relaxation)',
                    'sc_st': '37 years (5 years relaxation)',
                    'pwd': '42 years (10 years relaxation)',
                },
                'nationality': 'Indian citizen (also Nepal/Bhutan subjects, Tibetan refugees pre-1962)',
                'attempts': {
                    'general': '6 attempts',
                    'obc': '9 attempts',
                    'sc_st': 'Unlimited (up to age limit)',
                },
            },
            'paper_pattern': {
                'paper1': {
                    'title': 'Paper I',
                    'total_marks': 250,
                    'total_questions': 120,
                    'duration_minutes': 120,
                    'subjects': [
                        {'name': 'General Medicine', 'questions': 96, 'marks': 200},
                        {'name': 'Pediatrics', 'questions': 24, 'marks': 50},
                    ],
                },
                'paper2': {
                    'title': 'Paper II',
                    'total_marks': 250,
                    'total_questions': 120,
                    'duration_minutes': 120,
                    'subjects': [
                        {'name': 'Surgery', 'questions': 40, 'marks': 83.33},
                        {'name': 'Obstetrics & Gynecology', 'questions': 40, 'marks': 83.33},
                        {'name': 'Preventive & Social Medicine', 'questions': 40, 'marks': 83.33},
                    ],
                },
            },
            'marking_scheme': {
                'correct': '+2.08 marks per question (approx)',
                'incorrect': '-0.69 marks per question (1/3 negative marking)',
                'unanswered': '0 marks',
            },
            'personality_test': {
                'marks': 100,
                'description': 'Interview assessing general knowledge, academic ability, intellectual curiosity, critical thinking, judgment, social cohesion, integrity, leadership',
            },
            'recruiting_for': [
                'Assistant Divisional Medical Officer (ADMO) in Railways',
                'Assistant Medical Officer (AMO) in NDMC/MCD',
                'Junior Scale Posts in CHS (Central Health Service)',
                'General Duty Medical Officer (GDMO) in various central departments',
            ],
            'salary': {
                'pay_level': 'Level 10 (₹56,100 - ₹1,77,500)',
                'gross_monthly': '₹80,000 - ₹1,00,000 approx (including allowances)',
                'perks': 'Government quarters, medical facilities, LTC, pension, job security',
            },
            'standard_textbooks': [
                {'subject': 'Medicine', 'books': ["Harrison's Principles of Internal Medicine", "Davidson's Principles and Practice of Medicine"]},
                {'subject': 'Pediatrics', 'books': ['Ghai Essential Pediatrics', 'Nelson Textbook of Pediatrics', 'OP Ghai']},
                {'subject': 'Surgery', 'books': ["Bailey & Love's Short Practice of Surgery", "SRB's Manual of Surgery"]},
                {'subject': 'OBG', 'books': ["Shaw's Textbook of Gynecology", "DC Dutta's Textbook of Obstetrics"]},
                {'subject': 'PSM', 'books': ["Park's Textbook of Preventive and Social Medicine", 'Vivek Jain PSM']},
            ],
            'faq': [
                {'q': 'Can MBBS final-year students apply?', 'a': 'Yes, final-year students and those who have not completed internship can apply provisionally. However, they must complete internship before the date of appointment.'},
                {'q': 'Is OBC certificate format important?', 'a': 'Yes, it must be in the Central Government format (not state format). It must mention non-creamy layer status and be issued within the correct financial year.'},
                {'q': 'What documents are required for DAF?', 'a': 'Passport-size photo, signature, ID proof, MBBS degree/provisional certificate, internship certificate, category certificate (if applicable), date of birth proof (matriculation certificate).'},
                {'q': 'Can I choose my posting location?', 'a': 'You can fill preferences during counseling. Posts are allotted based on your rank, category, and availability. Top ranks get better choices.'},
                {'q': 'What is the expected salary?', 'a': 'Starting salary is approximately ₹80,000-1,00,000 per month (Pay Level 10) including DA, HRA and other allowances. This varies by posting location.'},
                {'q': 'How many attempts are allowed?', 'a': 'General: 6 attempts, OBC: 9 attempts, SC/ST: unlimited (within age limit). Each appearance counts as one attempt.'},
                {'q': 'Is there negative marking?', 'a': 'Yes, 1/3 of marks assigned to a question are deducted for each wrong answer. So approximately -0.69 marks per wrong answer.'},
                {'q': 'When does UPSC release the notification?', 'a': 'Usually in March-April. The exam is typically held in July-August. Check the official UPSC website for exact dates.'},
                {'q': 'Can foreign medical graduates apply?', 'a': 'Yes, but they must have cleared the FMGE (Foreign Medical Graduate Examination) conducted by NBE before document verification.'},
                {'q': 'What is the selection process after written exam?', 'a': 'Candidates qualifying the written exam are called for a Personality Test (Interview) of 100 marks. Final merit is based on written exam (500) + interview (100) = 600 marks total.'},
            ],
        }
        return Response(guide)
