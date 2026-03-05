"""
Management command to scrape PYQs from the enriched Medura_Train MD files
and populate the database with comprehensive CMS question data.

Run: python manage.py scrape_pyqs
     python manage.py scrape_pyqs --stats
     python manage.py scrape_pyqs --force  (re-import all)
"""
import re
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from questions.models import Subject, Topic, Question


# Subject/topic inference lookup
SUBJECT_MAP = {
    'cardiology': ('MED', 'Cardiology'),
    'nephrology': ('MED', 'Nephrology'),
    'neurology': ('MED', 'Neurology'),
    'endocrinology': ('MED', 'Endocrinology'),
    'pulmonology': ('MED', 'Pulmonology'),
    'gastroenterology': ('MED', 'Gastroenterology'),
    'hematology': ('MED', 'Hematology'),
    'rheumatology': ('MED', 'Rheumatology'),
    'infectious disease': ('MED', 'Infectious Disease'),
    'dermatology': ('MED', 'Dermatology'),
    'pharmacology': ('MED', 'Pharmacology'),
    'psychiatry': ('MED', 'Psychiatry'),
    'general medicine': ('MED', 'Cardiology'),
    'medicine': ('MED', 'Cardiology'),

    'neonatology': ('PED', 'Neonatology'),
    'growth': ('PED', 'Growth & Development'),
    'immunization': ('PED', 'Immunization'),
    'pediatric nutrition': ('PED', 'Pediatric Nutrition'),
    'pediatric': ('PED', 'Neonatology'),
    'pediatrics': ('PED', 'Neonatology'),

    'general surgery': ('SUR', 'General Surgery'),
    'trauma': ('SUR', 'Trauma'),
    'orthopedics': ('SUR', 'Orthopedics'),
    'urology': ('SUR', 'Urology'),
    'neurosurgery': ('SUR', 'Neurosurgery'),
    'anesthesia': ('SUR', 'Anesthesia'),
    'surgery': ('SUR', 'General Surgery'),
    'ophthalmology': ('SUR', 'General Surgery'),
    'ent': ('SUR', 'General Surgery'),

    'obstetrics': ('OBG', 'Obstetrics - Normal'),
    'gynecology': ('OBG', 'Gynecology'),
    'gynaecology': ('OBG', 'Gynecology'),
    'contraception': ('OBG', 'Contraception'),
    'obg': ('OBG', 'Obstetrics - Normal'),

    'biostatistics': ('PSM', 'Biostatistics'),
    'epidemiology': ('PSM', 'Epidemiology'),
    'nutrition': ('PSM', 'Nutrition'),
    'communicable': ('PSM', 'Communicable Diseases'),
    'health programs': ('PSM', 'Health Programs'),
    'environmental': ('PSM', 'Environmental Health'),
    'demography': ('PSM', 'Demography'),
    'occupational': ('PSM', 'Occupational Health'),
    'psm': ('PSM', 'Epidemiology'),
    'preventive': ('PSM', 'Epidemiology'),
}


def infer_subject_topic(section_header, question_text):
    """Infer subject code and topic name from section header and question text."""
    combined = f"{section_header} {question_text}".lower()
    for keyword, (subj_code, topic_name) in SUBJECT_MAP.items():
        if keyword in combined:
            return subj_code, topic_name
    return 'MED', 'Cardiology'


def parse_pyq_md(file_path):
    """Parse the PYQ markdown file and extract structured questions."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    questions = []
    current_section = ""
    current_paper = 1

    # Track section headers for subject inference
    lines = content.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Track section headers
        if line.startswith('## PAPER 2'):
            current_paper = 2
        elif line.startswith('## PAPER 1'):
            current_paper = 1
        elif line.startswith('### '):
            current_section = line.replace('### ', '').strip()
        elif line.startswith('**Q') and '[' in line and ']' in line:
            # Parse question block
            q_data = _parse_question_block(lines, i, current_section, current_paper)
            if q_data:
                questions.append(q_data)
        i += 1

    return questions


def _parse_question_block(lines, start_idx, section, paper):
    """Parse a single question block starting at start_idx."""
    try:
        header_line = lines[start_idx].strip()

        # Extract year from header like **Q1 [2024 Paper 1]**:
        year_match = re.search(r'\[(\d{4})', header_line)
        year = int(year_match.group(1)) if year_match else 2023

        # Extract question text (after ]: or :**)
        q_text_match = re.search(r'\]\*?\*?:?\s*(.+)', header_line)
        question_text = q_text_match.group(1).strip() if q_text_match else ""

        # Parse options (next lines starting with - A), - B), etc.)
        options = {'A': '', 'B': '', 'C': '', 'D': ''}
        i = start_idx + 1
        while i < len(lines) and i < start_idx + 10:
            line = lines[i].strip()
            opt_match = re.match(r'^-\s*([A-D])\)\s*(.+)', line)
            if opt_match:
                options[opt_match.group(1)] = opt_match.group(2).strip()
            elif line.startswith('**Answer:'):
                break
            i += 1

        # Parse answer line
        answer = ''
        explanation = ''
        while i < len(lines) and i < start_idx + 15:
            line = lines[i].strip()
            if line.startswith('**Answer:') or line.startswith('**Answer :'):
                ans_match = re.search(r'\*\*Answer\s*:\s*([A-D])\*?\*?\s*(.*)', line)
                if ans_match:
                    answer = ans_match.group(1)
                    explanation = ans_match.group(2).strip()
                break
            i += 1

        # Continue reading explanation and metadata
        textbook_ref = ''
        tags = []
        i += 1
        while i < len(lines) and i < start_idx + 20:
            line = lines[i].strip()
            if line.startswith('**Q') or line.startswith('### ') or line.startswith('## '):
                break
            if line.startswith('**Textbook Reference:'):
                textbook_ref = line.replace('**Textbook Reference:', '').replace('**', '').strip()
            if '[High Yield]' in line:
                tags.append('high_yield')
            pyq_tags = re.findall(r'\[PYQ (\d{4})\]', line)
            for yr in pyq_tags:
                tags.append(f'PYQ_{yr}')
            # Append extra explanation text
            if line and not line.startswith('**') and not line.startswith('[') and not line.startswith('---'):
                if explanation and not line.startswith('-'):
                    explanation += ' ' + line
            i += 1

        if not question_text or not answer:
            return None

        # Infer subject and topic
        subj_code, topic_name = infer_subject_topic(section, question_text)

        # Extract concept keywords from question
        keywords = _extract_keywords(question_text, explanation)

        return {
            'question_text': question_text,
            'option_a': options.get('A', ''),
            'option_b': options.get('B', ''),
            'option_c': options.get('C', ''),
            'option_d': options.get('D', ''),
            'correct_answer': answer,
            'year': year,
            'paper': paper,
            'subject_code': subj_code,
            'topic_name': topic_name,
            'difficulty': _estimate_difficulty(question_text, tags),
            'explanation': explanation,
            'book_name': textbook_ref.split(',')[0].strip() if textbook_ref else '',
            'chapter': textbook_ref.split(',')[1].strip() if ',' in textbook_ref else textbook_ref,
            'concept_tags': tags,
            'concept_keywords': keywords,
            'exam_source': 'UPSC CMS',
            'times_asked': len([t for t in tags if t.startswith('PYQ_')]),
        }
    except Exception:
        return None


def _estimate_difficulty(question_text, tags):
    """Estimate difficulty based on question complexity."""
    text_lower = question_text.lower()
    hard_keywords = ['except', 'false', 'not true', 'incorrect', 'all of the following',
                     'mechanism', 'pathophysiology', 'least likely']
    easy_keywords = ['most common', 'first line', 'diagnostic', 'gold standard',
                     'characteristic', 'pathognomonic']

    if any(kw in text_lower for kw in hard_keywords):
        return 'hard'
    if any(kw in text_lower for kw in easy_keywords):
        return 'easy'
    return 'medium'


def _extract_keywords(question_text, explanation):
    """Extract concept keywords from question and explanation."""
    # Medical keyword patterns
    medical_terms = re.findall(r'\b[A-Z][a-z]+(?:\'s)?\b', f"{question_text} {explanation}")
    # Filter common words
    stop_words = {'The', 'Which', 'What', 'Most', 'All', 'Following', 'Except',
                  'Given', 'Patient', 'Presents', 'Year', 'Old', 'Male', 'Female',
                  'Common', 'Cause', 'Best', 'First', 'Treatment', 'Diagnosis',
                  'Shows', 'Test', 'Used', 'Seen', 'Associated', 'Include', 'NOT'}
    keywords = list(set([t for t in medical_terms if t not in stop_words]))[:15]
    return keywords


class Command(BaseCommand):
    help = 'Scrape PYQs from Medura_Train MD files and populate the database'

    def add_arguments(self, parser):
        parser.add_argument('--stats', action='store_true', help='Show stats only')
        parser.add_argument('--force', action='store_true', help='Re-import all questions')

    def handle(self, *args, **options):
        if options['stats']:
            self._show_stats()
            return

        self.stdout.write('\n🔍 Scraping PYQs from Medura_Train...\n')

        # Ensure subjects and topics exist
        self._ensure_subjects_topics()

        # Find PYQ files
        train_dir = getattr(settings, 'MEDURA_TRAIN_DIR', settings.BASE_DIR / 'Medura_Train')
        pyq_dir = os.path.join(train_dir, 'PYQ')

        total_created = 0
        total_skipped = 0

        if os.path.exists(pyq_dir):
            for f in os.listdir(pyq_dir):
                if f.endswith('.md') or f.endswith('.txt'):
                    file_path = os.path.join(pyq_dir, f)
                    self.stdout.write(f'  📄 Parsing: {f}')
                    questions = parse_pyq_md(file_path)
                    self.stdout.write(f'     Found {len(questions)} questions')

                    for q_data in questions:
                        created = self._save_question(q_data, force=options['force'])
                        if created:
                            total_created += 1
                        else:
                            total_skipped += 1

        # Also seed additional high-yield questions not in the MD file
        extra_created = self._seed_extra_pyqs()
        total_created += extra_created

        self.stdout.write(self.style.SUCCESS(
            f'\n✅ PYQ scraping complete!'
            f'\n  Created: {total_created}'
            f'\n  Skipped (already exist): {total_skipped}'
            f'\n  Total in DB: {Question.objects.count()}'
        ))
        self._show_stats()

    def _ensure_subjects_topics(self):
        """Make sure all subjects and topics exist."""
        subjects_data = [
            {'name': 'General Medicine', 'code': 'MED', 'paper': 1, 'icon': '🫀', 'color': '#EF4444',
             'description': 'Internal medicine including all medical specialties'},
            {'name': 'Pediatrics', 'code': 'PED', 'paper': 1, 'icon': '👶', 'color': '#F59E0B',
             'description': 'Child health and neonatal medicine'},
            {'name': 'Surgery', 'code': 'SUR', 'paper': 2, 'icon': '🔪', 'color': '#3B82F6',
             'description': 'General and specialized surgery'},
            {'name': 'Obstetrics & Gynecology', 'code': 'OBG', 'paper': 2, 'icon': '🤰', 'color': '#EC4899',
             'description': 'Maternal and reproductive health'},
            {'name': 'Preventive & Social Medicine', 'code': 'PSM', 'paper': 2, 'icon': '📊', 'color': '#10B981',
             'description': 'Community medicine, biostatistics, epidemiology'},
        ]
        for s in subjects_data:
            Subject.objects.get_or_create(code=s['code'], defaults=s)

        topics_data = {
            'MED': ['Cardiology', 'Nephrology', 'Neurology', 'Pulmonology', 'Gastroenterology',
                     'Endocrinology', 'Hematology', 'Rheumatology', 'Infectious Disease',
                     'Dermatology', 'Psychiatry', 'Pharmacology'],
            'PED': ['Neonatology', 'Growth & Development', 'Immunization', 'Pediatric Nutrition',
                     'Pediatric Cardiology', 'Genetic Disorders', 'Pediatric Neurology', 'Pediatric Infections'],
            'SUR': ['General Surgery', 'Trauma', 'Orthopedics', 'Urology', 'Neurosurgery',
                     'Cardiothoracic Surgery', 'Plastic Surgery', 'Surgical Oncology', 'Anesthesia'],
            'OBG': ['Obstetrics - Normal', 'Obstetrics - High Risk', 'Gynecology', 'Infertility',
                     'Contraception', 'Gynecological Oncology', 'Menstrual Disorders', 'Pelvic Floor Disorders'],
            'PSM': ['Biostatistics', 'Epidemiology', 'Nutrition', 'Communicable Diseases',
                     'Non-communicable Diseases', 'Health Programs', 'Environmental Health',
                     'Demography', 'Health Administration', 'Occupational Health'],
        }
        for code, topic_names in topics_data.items():
            subject = Subject.objects.get(code=code)
            for name in topic_names:
                Topic.objects.get_or_create(subject=subject, name=name, defaults={'importance': 7})

    def _save_question(self, q_data, force=False):
        """Save a parsed question to the database. Returns True if created."""
        try:
            subject = Subject.objects.get(code=q_data['subject_code'])
            topic = Topic.objects.filter(
                subject=subject, name=q_data['topic_name']
            ).first()
            if not topic:
                topic = Topic.objects.filter(subject=subject).first()

            defaults = {
                'option_a': q_data['option_a'],
                'option_b': q_data['option_b'],
                'option_c': q_data['option_c'],
                'option_d': q_data['option_d'],
                'correct_answer': q_data['correct_answer'],
                'subject': subject,
                'topic': topic,
                'difficulty': q_data['difficulty'],
                'explanation': q_data['explanation'],
                'book_name': q_data.get('book_name', ''),
                'chapter': q_data.get('chapter', ''),
                'concept_tags': q_data.get('concept_tags', []),
                'concept_keywords': q_data.get('concept_keywords', []),
                'exam_source': 'UPSC CMS',
                'paper': q_data.get('paper', 0),
                'times_asked': q_data.get('times_asked', 1),
            }

            if force:
                Question.objects.filter(
                    question_text=q_data['question_text'], year=q_data['year']
                ).delete()

            _, created = Question.objects.get_or_create(
                question_text=q_data['question_text'],
                year=q_data['year'],
                defaults=defaults,
            )
            return created
        except Exception as e:
            self.stderr.write(f'  ⚠️ Error saving question: {e}')
            return False

    def _seed_extra_pyqs(self):
        """Seed additional high-yield PYQ questions not in the MD file."""
        extra_questions = [
            # Extra Medicine Questions
            {
                'question_text': 'Kayser-Fleischer ring is seen in which condition?',
                'option_a': 'Hemochromatosis', 'option_b': 'Wilson disease',
                'option_c': "Parkinson's disease", 'option_d': 'Multiple sclerosis',
                'correct_answer': 'B', 'year': 2019, 'paper': 1,
                'subject_code': 'MED', 'topic_name': 'Gastroenterology',
                'difficulty': 'easy',
                'explanation': 'Kayser-Fleischer (KF) ring is golden-brown ring at the periphery of cornea due to copper deposition in Descemet membrane. Pathognomonic of Wilson disease (hepatolenticular degeneration).',
                'concept_tags': ['high_yield', 'PYQ_2019'],
                'concept_keywords': ['KF ring', 'Wilson', 'copper', 'Descemet'],
            },
            {
                'question_text': 'Drug of choice for status epilepticus is:',
                'option_a': 'Phenytoin', 'option_b': 'Carbamazepine',
                'option_c': 'Lorazepam', 'option_d': 'Sodium valproate',
                'correct_answer': 'C', 'year': 2020, 'paper': 1,
                'subject_code': 'MED', 'topic_name': 'Neurology',
                'difficulty': 'easy',
                'explanation': 'IV Lorazepam (or diazepam) is first-line for status epilepticus. If seizures persist, IV phenytoin/fosphenytoin is added. Refractory cases: midazolam/propofol infusion.',
                'concept_tags': ['high_yield', 'PYQ_2020'],
                'concept_keywords': ['status epilepticus', 'lorazepam', 'seizure'],
            },
            {
                'question_text': 'Reed-Sternberg cells are pathognomonic of:',
                'option_a': "Non-Hodgkin's lymphoma", 'option_b': "Hodgkin's lymphoma",
                'option_c': 'Multiple myeloma', 'option_d': 'CLL',
                'correct_answer': 'B', 'year': 2021, 'paper': 1,
                'subject_code': 'MED', 'topic_name': 'Hematology',
                'difficulty': 'easy',
                'explanation': 'Reed-Sternberg cells (owl-eye appearance, bilobed nucleus) are pathognomonic of Hodgkin lymphoma. They are CD15+ and CD30+ giant cells.',
                'concept_tags': ['high_yield', 'PYQ_2021'],
                'concept_keywords': ['Reed-Sternberg', 'Hodgkin', 'lymphoma', 'owl-eye'],
            },
            # Extra Pediatrics Questions
            {
                'question_text': 'Social smile appears at what age in an infant?',
                'option_a': '2 weeks', 'option_b': '6 weeks',
                'option_c': '3 months', 'option_d': '4 months',
                'correct_answer': 'B', 'year': 2022, 'paper': 1,
                'subject_code': 'PED', 'topic_name': 'Growth & Development',
                'difficulty': 'easy',
                'explanation': 'Social smile appears at 6 weeks (responsive smile to mother). Spontaneous smile may be seen at birth. Other milestones: Head holding 3mo, Sitting 6mo, Standing 9mo, Walking 12mo.',
                'concept_tags': ['high_yield', 'PYQ_2022'],
                'concept_keywords': ['social smile', 'milestone', 'development'],
            },
            {
                'question_text': 'Most common congenital heart disease is:',
                'option_a': 'ASD', 'option_b': 'VSD',
                'option_c': 'PDA', 'option_d': 'TOF',
                'correct_answer': 'B', 'year': 2023, 'paper': 1,
                'subject_code': 'PED', 'topic_name': 'Pediatric Cardiology',
                'difficulty': 'easy',
                'explanation': 'VSD is the most common congenital heart disease overall. ASD is the most common acyanotic CHD presenting in adults. TOF is the most common cyanotic CHD.',
                'concept_tags': ['high_yield', 'PYQ_2023', 'PYQ_2020'],
                'concept_keywords': ['VSD', 'congenital heart', 'CHD'],
            },
            {
                'question_text': 'Kernicterus is caused by deposition of which substance in the brain?',
                'option_a': 'Conjugated bilirubin', 'option_b': 'Unconjugated bilirubin',
                'option_c': 'Iron', 'option_d': 'Copper',
                'correct_answer': 'B', 'year': 2019, 'paper': 1,
                'subject_code': 'PED', 'topic_name': 'Neonatology',
                'difficulty': 'medium',
                'explanation': 'Kernicterus = unconjugated (indirect) bilirubin deposition in basal ganglia. Only unconjugated bilirubin crosses BBB. Causes include Rh incompatibility, G6PD deficiency.',
                'concept_tags': ['high_yield', 'PYQ_2019'],
                'concept_keywords': ['kernicterus', 'bilirubin', 'unconjugated', 'basal ganglia'],
            },
            # Extra Surgery Questions
            {
                'question_text': 'Charcot triad is seen in:',
                'option_a': 'Acute pancreatitis', 'option_b': 'Acute cholangitis',
                'option_c': 'Acute appendicitis', 'option_d': 'Acute cholecystitis',
                'correct_answer': 'B', 'year': 2023, 'paper': 2,
                'subject_code': 'SUR', 'topic_name': 'General Surgery',
                'difficulty': 'easy',
                'explanation': 'Charcot triad (fever + jaundice + RUQ pain) = acute cholangitis. Reynolds pentad adds  hypotension + altered mental status = severe/toxic cholangitis.',
                'concept_tags': ['high_yield', 'PYQ_2023'],
                'concept_keywords': ['Charcot triad', 'cholangitis', 'jaundice'],
            },
            {
                'question_text': 'Most common type of intestinal obstruction in India is:',
                'option_a': 'Adhesions', 'option_b': 'Obstructed hernia',
                'option_c': 'Volvulus', 'option_d': 'Intussusception',
                'correct_answer': 'B', 'year': 2021, 'paper': 2,
                'subject_code': 'SUR', 'topic_name': 'General Surgery',
                'difficulty': 'medium',
                'explanation': 'In India, obstructed/strangulated hernia is the MC cause of intestinal obstruction. In Western countries, adhesions (post-operative) are the MC cause.',
                'concept_tags': ['PYQ_2021'],
                'concept_keywords': ['intestinal obstruction', 'hernia', 'adhesions'],
            },
            {
                'question_text': 'Garden classification is used for:',
                'option_a': 'Femoral neck fractures', 'option_b': 'Intertrochanteric fractures',
                'option_c': 'Colles fracture', 'option_d': 'Supracondylar fracture',
                'correct_answer': 'A', 'year': 2022, 'paper': 2,
                'subject_code': 'SUR', 'topic_name': 'Orthopedics',
                'difficulty': 'medium',
                'explanation': 'Garden classification (I-IV) is for femoral neck (intracapsular) fractures based on displacement. Garden I-II = undisplaced (fixation), Garden III-IV = displaced (hemiarthroplasty in elderly).',
                'concept_tags': ['PYQ_2022'],
                'concept_keywords': ['Garden classification', 'femoral neck', 'fracture'],
            },
            # Extra OBG Questions
            {
                'question_text': 'Most reliable sign of ovulation is:',
                'option_a': 'Rise in BBT', 'option_b': 'Cervical mucus ferning',
                'option_c': 'Secretory endometrium on biopsy', 'option_d': 'LH surge',
                'correct_answer': 'C', 'year': 2022, 'paper': 2,
                'subject_code': 'OBG', 'topic_name': 'Gynecology',
                'difficulty': 'medium',
                'explanation': 'Secretory endometrium on biopsy is the MOST RELIABLE proof that ovulation has occurred. LH surge predicts ovulation. BBT rises after ovulation (progesterone effect).',
                'concept_tags': ['high_yield', 'PYQ_2022'],
                'concept_keywords': ['ovulation', 'secretory endometrium', 'BBT', 'LH'],
            },
            {
                'question_text': 'Drug of choice for eclampsia is:',
                'option_a': 'Diazepam', 'option_b': 'Phenytoin',
                'option_c': 'Magnesium sulfate', 'option_d': 'Labetalol',
                'correct_answer': 'C', 'year': 2024, 'paper': 2,
                'subject_code': 'OBG', 'topic_name': 'Obstetrics - High Risk',
                'difficulty': 'easy',
                'explanation': 'MgSO4 (Pritchard/Zuspan regimen) is the drug of choice for both prevention and treatment of eclampsia. It is superior to diazepam and phenytoin (MAGPIE trial).',
                'concept_tags': ['high_yield', 'PYQ_2024', 'PYQ_2021', 'PYQ_2019'],
                'concept_keywords': ['eclampsia', 'MgSO4', 'Pritchard', 'MAGPIE'],
            },
            {
                'question_text': 'IUCD with highest efficacy is:',
                'option_a': 'Copper T 200', 'option_b': 'Copper T 380A',
                'option_c': 'LNG-IUS (Mirena)', 'option_d': 'Multiload 375',
                'correct_answer': 'C', 'year': 2020, 'paper': 2,
                'subject_code': 'OBG', 'topic_name': 'Contraception',
                'difficulty': 'medium',
                'explanation': 'LNG-IUS (Mirena) has the lowest failure rate (0.1%) among all IUCDs. It also treats menorrhagia. Copper T 380A is the most widely used non-hormonal IUCD worldwide.',
                'concept_tags': ['PYQ_2020'],
                'concept_keywords': ['IUCD', 'Mirena', 'LNG-IUS', 'contraception'],
            },
            # Extra PSM Questions
            {
                'question_text': 'Sensitivity of a screening test is defined as:',
                'option_a': 'True positives / (True positives + False negatives)',
                'option_b': 'True negatives / (True negatives + False positives)',
                'option_c': 'True positives / (True positives + False positives)',
                'option_d': 'True negatives / (True negatives + False negatives)',
                'correct_answer': 'A', 'year': 2023, 'paper': 2,
                'subject_code': 'PSM', 'topic_name': 'Biostatistics',
                'difficulty': 'easy',
                'explanation': 'Sensitivity = TP/(TP+FN) = ability to detect disease. Specificity = TN/(TN+FP) = ability to rule out. PPV = TP/(TP+FP). NPV = TN/(TN+FN).',
                'concept_tags': ['high_yield', 'PYQ_2023', 'PYQ_2021'],
                'concept_keywords': ['sensitivity', 'specificity', 'screening', 'PPV', 'NPV'],
            },
            {
                'question_text': 'National Health Mission (NHM) includes:',
                'option_a': 'NRHM only', 'option_b': 'NUHM only',
                'option_c': 'Both NRHM and NUHM', 'option_d': 'Neither',
                'correct_answer': 'C', 'year': 2022, 'paper': 2,
                'subject_code': 'PSM', 'topic_name': 'Health Programs',
                'difficulty': 'easy',
                'explanation': 'NHM (2013) encompasses both NRHM (National Rural Health Mission, 2005) and NUHM (National Urban Health Mission). Goal: universal access to equitable, quality healthcare.',
                'concept_tags': ['PYQ_2022'],
                'concept_keywords': ['NHM', 'NRHM', 'NUHM', 'health mission'],
            },
            {
                'question_text': 'Herd immunity threshold for measles is approximately:',
                'option_a': '50%', 'option_b': '70%',
                'option_c': '83-94%', 'option_d': '99%',
                'correct_answer': 'C', 'year': 2021, 'paper': 2,
                'subject_code': 'PSM', 'topic_name': 'Communicable Diseases',
                'difficulty': 'medium',
                'explanation': 'Measles (R0=12-18) requires 83-94% herd immunity. Formula: HIT = 1 - 1/R0. Higher R0 = higher threshold needed. COVID R0=2-3 needs ~60-70%.',
                'concept_tags': ['high_yield', 'PYQ_2021'],
                'concept_keywords': ['herd immunity', 'measles', 'R0', 'threshold'],
            },
            {
                'question_text': 'Infant Mortality Rate (IMR) is defined as deaths under 1 year per:',
                'option_a': '100 live births', 'option_b': '1000 live births',
                'option_c': '1000 total births', 'option_d': '100,000 population',
                'correct_answer': 'B', 'year': 2020, 'paper': 2,
                'subject_code': 'PSM', 'topic_name': 'Demography',
                'difficulty': 'easy',
                'explanation': 'IMR = Deaths <1 year / 1000 live births in that year. NMR = <28 days. PMR = <7 days. IMR is the most sensitive index of health status of a community.',
                'concept_tags': ['high_yield', 'PYQ_2020', 'PYQ_2018'],
                'concept_keywords': ['IMR', 'infant mortality', 'NMR', 'health index'],
            },
            {
                'question_text': 'Protein Energy Malnutrition (PEM) - Kwashiorkor is characterized by:',
                'option_a': 'Marasmus + infections', 'option_b': 'Predominantly protein deficiency with edema',
                'option_c': 'Predominantly calorie deficiency', 'option_d': 'Vitamin A deficiency',
                'correct_answer': 'B', 'year': 2019, 'paper': 2,
                'subject_code': 'PSM', 'topic_name': 'Nutrition',
                'difficulty': 'easy',
                'explanation': 'Kwashiorkor = protein deficiency → edema, fatty liver, flag sign hair, moon face, miserable. Marasmus = calorie deficiency → wasting, monkey facies, old man appearance, alert.',
                'concept_tags': ['high_yield', 'PYQ_2019'],
                'concept_keywords': ['Kwashiorkor', 'Marasmus', 'PEM', 'protein deficiency'],
            },
        ]

        created_count = 0
        for q_data in extra_questions:
            if self._save_question(q_data):
                created_count += 1
        return created_count

    def _show_stats(self):
        """Show database statistics."""
        self.stdout.write('\n📊 Database Statistics:')
        self.stdout.write(f'  Total Questions: {Question.objects.count()}')
        self.stdout.write(f'  Subjects: {Subject.objects.count()}')
        self.stdout.write(f'  Topics: {Topic.objects.count()}')
        self.stdout.write('\n  Per Subject:')
        for subject in Subject.objects.all():
            count = Question.objects.filter(subject=subject).count()
            self.stdout.write(f'    {subject.name}: {count} questions')
        self.stdout.write('\n  Per Year:')
        from django.db.models import Count
        year_counts = Question.objects.values('year').annotate(count=Count('id')).order_by('year')
        for yc in year_counts:
            self.stdout.write(f'    {yc["year"]}: {yc["count"]} questions')
