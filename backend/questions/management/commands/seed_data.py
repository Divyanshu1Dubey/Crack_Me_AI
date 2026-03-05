"""
Management command to seed the database with sample UPSC CMS questions.
Run: python manage.py seed_data
"""
from django.core.management.base import BaseCommand
from questions.models import Subject, Topic, Question


class Command(BaseCommand):
    help = 'Seeds the database with sample UPSC CMS questions and subjects'

    def handle(self, *args, **options):
        self.stdout.write('🏥 Seeding UPSC CMS database...\n')

        # Create Subjects
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

        subjects = {}
        for s_data in subjects_data:
            subject, created = Subject.objects.get_or_create(
                code=s_data['code'],
                defaults=s_data
            )
            subjects[s_data['code']] = subject
            status = '✅ Created' if created else '⏭ Exists'
            self.stdout.write(f'  {status}: {subject.name}')

        # Create Topics
        topics_data = {
            'MED': [
                'Cardiology', 'Nephrology', 'Neurology', 'Pulmonology',
                'Gastroenterology', 'Endocrinology', 'Hematology', 'Rheumatology',
                'Infectious Disease', 'Dermatology', 'Psychiatry', 'Pharmacology',
            ],
            'PED': [
                'Neonatology', 'Growth & Development', 'Immunization',
                'Pediatric Nutrition', 'Pediatric Cardiology', 'Genetic Disorders',
                'Pediatric Neurology', 'Pediatric Infections',
            ],
            'SUR': [
                'General Surgery', 'Trauma', 'Orthopedics', 'Urology',
                'Neurosurgery', 'Cardiothoracic Surgery', 'Plastic Surgery',
                'Surgical Oncology', 'Anesthesia',
            ],
            'OBG': [
                'Obstetrics - Normal', 'Obstetrics - High Risk', 'Gynecology',
                'Infertility', 'Contraception', 'Gynecological Oncology',
                'Menstrual Disorders', 'Pelvic Floor Disorders',
            ],
            'PSM': [
                'Biostatistics', 'Epidemiology', 'Nutrition',
                'Communicable Diseases', 'Non-communicable Diseases',
                'Health Programs', 'Environmental Health', 'Demography',
                'Health Administration', 'Occupational Health',
            ],
        }

        topics = {}
        for code, topic_names in topics_data.items():
            for t_name in topic_names:
                topic, created = Topic.objects.get_or_create(
                    subject=subjects[code],
                    name=t_name,
                    defaults={'importance': 7}
                )
                topics[f"{code}_{t_name}"] = topic

        self.stdout.write(f'\n📚 Created {Topic.objects.count()} topics\n')

        # Create Sample Questions
        questions = [
            # Medicine - Cardiology
            {
                'question_text': 'Which of the following is the most common cause of acute myocardial infarction?',
                'option_a': 'Coronary artery thrombosis',
                'option_b': 'Coronary artery spasm',
                'option_c': 'Aortic dissection',
                'option_d': 'Coronary artery embolism',
                'correct_answer': 'A',
                'year': 2023,
                'subject': subjects['MED'],
                'topic': topics.get('MED_Cardiology'),
                'difficulty': 'easy',
                'concept_tags': ['AMI', 'coronary thrombosis', 'atherosclerosis'],
                'explanation': 'Coronary artery thrombosis due to rupture of atherosclerotic plaque is the most common cause of acute MI. The thrombus forms on a disrupted plaque and occludes the vessel.',
                'concept_explanation': 'Acute MI occurs when blood supply to the myocardium is interrupted. The most common mechanism is atherosclerotic plaque rupture → platelet aggregation → thrombus formation → coronary occlusion → myocardial necrosis.',
                'mnemonic': 'THROMBUS: Thrombosis Halts Regular Oxygen supply to Myocardium By Unstable plaque Shedding',
                'book_name': 'Harrison\'s Principles of Internal Medicine',
                'chapter': 'Acute Myocardial Infarction',
                'page_number': '1874',
                'exam_source': 'UPSC CMS',
            },
            # Medicine - Nephrology
            {
                'question_text': 'Which of the following is NOT a feature of nephrotic syndrome?',
                'option_a': 'Proteinuria > 3.5 g/day',
                'option_b': 'Hypoalbuminemia',
                'option_c': 'Hematuria',
                'option_d': 'Hyperlipidemia',
                'correct_answer': 'C',
                'year': 2022,
                'subject': subjects['MED'],
                'topic': topics.get('MED_Nephrology'),
                'difficulty': 'medium',
                'concept_tags': ['nephrotic syndrome', 'proteinuria', 'kidney'],
                'explanation': 'Nephrotic syndrome consists of: heavy proteinuria (>3.5g/day), hypoalbuminemia, hyperlipidemia, lipiduria, and edema. Hematuria is characteristic of NEPHRITIC syndrome, not nephrotic.',
                'mnemonic': 'Nephrotic = "Protein leaks out": Proteinuria, hypoAlbuminemia, hyperLipidemia, Edema (PALE)',
                'book_name': 'Harrison\'s Principles of Internal Medicine',
                'chapter': 'Glomerular Diseases',
                'exam_source': 'UPSC CMS',
            },
            # Medicine - Endocrinology
            {
                'question_text': 'Chvostek sign is seen in which of the following conditions?',
                'option_a': 'Hypercalcemia',
                'option_b': 'Hypocalcemia',
                'option_c': 'Hyperkalemia',
                'option_d': 'Hyponatremia',
                'correct_answer': 'B',
                'year': 2021,
                'subject': subjects['MED'],
                'topic': topics.get('MED_Endocrinology'),
                'difficulty': 'easy',
                'concept_tags': ['Chvostek sign', 'hypocalcemia', 'tetany'],
                'explanation': 'Chvostek sign is twitching of facial muscles on tapping the facial nerve. It is a sign of neuromuscular excitability due to hypocalcemia. Trousseau sign (carpal spasm) is another sign of hypocalcemia.',
                'mnemonic': 'CHvostek = CHeck Calcium (Hypo). Tap the face → Twitch!',
                'book_name': 'Davidson\'s Principles and Practice of Medicine',
                'exam_source': 'UPSC CMS',
            },
            # Medicine - Neurology
            {
                'question_text': 'Argyll Robertson pupil is characteristically seen in:',
                'option_a': 'Multiple sclerosis',
                'option_b': 'Neurosyphilis',
                'option_c': 'Diabetes mellitus',
                'option_d': 'Migraine',
                'correct_answer': 'B',
                'year': 2020,
                'subject': subjects['MED'],
                'topic': topics.get('MED_Neurology'),
                'difficulty': 'medium',
                'concept_tags': ['Argyll Robertson pupil', 'neurosyphilis', 'pupil'],
                'explanation': 'Argyll Robertson pupil accommodates but does not react to light ("Accommodation Reflex Present" = ARP). It is pathognomonic of neurosyphilis.',
                'mnemonic': 'ARP = Accommodation Reflex Present. "Prostitute\'s pupil" - accommodates but doesn\'t react (like a prostitute who accommodates but doesn\'t react)',
                'book_name': 'Harrison\'s Principles of Internal Medicine',
                'exam_source': 'UPSC CMS',
            },
            # Pediatrics
            {
                'question_text': 'The first vaccine given to a newborn in India under the Universal Immunization Programme is:',
                'option_a': 'OPV',
                'option_b': 'BCG',
                'option_c': 'Hepatitis B (birth dose)',
                'option_d': 'Both BCG and OPV-0',
                'correct_answer': 'D',
                'year': 2023,
                'subject': subjects['PED'],
                'topic': topics.get('PED_Immunization'),
                'difficulty': 'easy',
                'concept_tags': ['immunization', 'newborn', 'BCG', 'OPV'],
                'explanation': 'Under India\'s UIP, at birth: BCG, OPV-0, and Hepatitis B birth dose are given. BCG and OPV-0 are the primary birth vaccines.',
                'mnemonic': 'Birth = BOH: BCG, OPV-0, Hep B',
                'book_name': 'Ghai Essential Pediatrics',
                'exam_source': 'UPSC CMS',
            },
            # Pediatrics - Neonatology
            {
                'question_text': 'In Apgar scoring, a score of 7-10 at 1 minute indicates:',
                'option_a': 'Severely depressed baby',
                'option_b': 'Moderately depressed baby',
                'option_c': 'Normal/vigorous baby',
                'option_d': 'Need for immediate intubation',
                'correct_answer': 'C',
                'year': 2021,
                'subject': subjects['PED'],
                'topic': topics.get('PED_Neonatology'),
                'difficulty': 'easy',
                'concept_tags': ['Apgar score', 'neonatal assessment', 'newborn'],
                'explanation': 'Apgar score: 7-10 = normal, 4-6 = moderate depression (needs stimulation), 0-3 = severe depression (needs resuscitation). Assessed at 1 and 5 minutes.',
                'mnemonic': 'APGAR: Appearance, Pulse, Grimace, Activity, Respiration',
                'book_name': 'Nelson Textbook of Pediatrics',
                'exam_source': 'UPSC CMS',
            },
            # Surgery
            {
                'question_text': 'Virchow\'s triad for venous thrombosis includes all EXCEPT:',
                'option_a': 'Venous stasis',
                'option_b': 'Hypercoagulability',
                'option_c': 'Endothelial injury',
                'option_d': 'Arterial hypertension',
                'correct_answer': 'D',
                'year': 2022,
                'subject': subjects['SUR'],
                'topic': topics.get('SUR_General Surgery'),
                'difficulty': 'easy',
                'concept_tags': ['Virchow triad', 'DVT', 'thrombosis'],
                'explanation': 'Virchow\'s triad: 1) Venous stasis (slow flow) 2) Hypercoagulability 3) Endothelial/vessel wall injury. Arterial hypertension is NOT part of the triad.',
                'mnemonic': 'SHE gets DVT: Stasis, Hypercoagulability, Endothelial injury',
                'book_name': 'Bailey & Love\'s Short Practice of Surgery',
                'exam_source': 'UPSC CMS',
            },
            # Surgery - Trauma
            {
                'question_text': 'In tension pneumothorax, the trachea deviates to:',
                'option_a': 'Same side as pneumothorax',
                'option_b': 'Opposite side of pneumothorax',
                'option_c': 'No deviation',
                'option_d': 'Anterior deviation',
                'correct_answer': 'B',
                'year': 2020,
                'subject': subjects['SUR'],
                'topic': topics.get('SUR_Trauma'),
                'difficulty': 'medium',
                'concept_tags': ['tension pneumothorax', 'tracheal deviation', 'trauma'],
                'explanation': 'In tension pneumothorax, air accumulates under pressure → mediastinal shift → trachea deviates AWAY from the affected side (opposite side). Emergency needle decompression at 2nd ICS, MCL.',
                'mnemonic': 'Tension pushes AWAY: Trachea pushed to opposite side',
                'book_name': 'Bailey & Love\'s Short Practice of Surgery',
                'exam_source': 'UPSC CMS',
            },
            # OBG
            {
                'question_text': 'Bishop score is used for assessment of:',
                'option_a': 'Fetal maturity',
                'option_b': 'Cervical favorability for induction',
                'option_c': 'Gestational age',
                'option_d': 'Placental grading',
                'correct_answer': 'B',
                'year': 2023,
                'subject': subjects['OBG'],
                'topic': topics.get('OBG_Obstetrics - Normal'),
                'difficulty': 'easy',
                'concept_tags': ['Bishop score', 'cervix', 'labor induction'],
                'explanation': 'Bishop score assesses cervical readiness for induction. Parameters: Dilatation, Effacement, Station, Consistency, Position. Score ≥ 8 = favorable for induction.',
                'mnemonic': 'BISHOP = cervix readiness. DECSP: Dilatation, Effacement, Consistency, Station, Position',
                'book_name': 'Shaw\'s Textbook of Gynecology',
                'exam_source': 'UPSC CMS',
            },
            # OBG - High Risk
            {
                'question_text': 'Most common cause of postpartum hemorrhage (PPH) is:',
                'option_a': 'Genital tract trauma',
                'option_b': 'Uterine atony',
                'option_c': 'Retained placenta',
                'option_d': 'Coagulation disorders',
                'correct_answer': 'B',
                'year': 2021,
                'subject': subjects['OBG'],
                'topic': topics.get('OBG_Obstetrics - High Risk'),
                'difficulty': 'easy',
                'concept_tags': ['PPH', 'uterine atony', 'postpartum'],
                'explanation': 'Uterine atony (failure of uterus to contract after delivery) is the MOST COMMON cause of PPH, accounting for ~80% cases. Remember the 4 T\'s of PPH.',
                'mnemonic': '4 T\'s of PPH: Tone (atony - MC), Trauma, Tissue (retained), Thrombin (coagulopathy)',
                'book_name': 'Shaw\'s Textbook of Gynecology',
                'exam_source': 'UPSC CMS',
            },
            # PSM - Biostatistics
            {
                'question_text': 'The measure of central tendency most affected by extreme values is:',
                'option_a': 'Median',
                'option_b': 'Mode',
                'option_c': 'Mean',
                'option_d': 'Geometric mean',
                'correct_answer': 'C',
                'year': 2022,
                'subject': subjects['PSM'],
                'topic': topics.get('PSM_Biostatistics'),
                'difficulty': 'easy',
                'concept_tags': ['mean', 'central tendency', 'statistics'],
                'explanation': 'Arithmetic mean is most affected by extreme values (outliers). Median and mode are resistant to outliers. That\'s why median is preferred for skewed distributions.',
                'mnemonic': 'Mean is MEAN — gets affected by extreme values. Median is MEDIAtor — stays in the middle.',
                'book_name': 'Park\'s Textbook of Preventive and Social Medicine',
                'exam_source': 'UPSC CMS',
            },
            # PSM - Epidemiology
            {
                'question_text': 'Incubation period of measles is:',
                'option_a': '1-3 days',
                'option_b': '10-14 days',
                'option_c': '21-28 days',
                'option_d': '5-7 days',
                'correct_answer': 'B',
                'year': 2019,
                'subject': subjects['PSM'],
                'topic': topics.get('PSM_Communicable Diseases'),
                'difficulty': 'easy',
                'concept_tags': ['measles', 'incubation period', 'communicable disease'],
                'explanation': 'Measles has an incubation period of 10-14 days (average 10 days). The prodromal period is 3-5 days with fever, cough, coryza, conjunctivitis, and Koplik spots.',
                'mnemonic': 'Measles = 10 letters = ~10 days incubation',
                'book_name': 'Park\'s Textbook of Preventive and Social Medicine',
                'exam_source': 'UPSC CMS',
            },
            # More complex questions
            {
                'question_text': 'Which investigation is the gold standard for diagnosis of pulmonary embolism?',
                'option_a': 'D-dimer',
                'option_b': 'CT Pulmonary Angiography',
                'option_c': 'Conventional Pulmonary Angiography',
                'option_d': 'V/Q scan',
                'correct_answer': 'C',
                'year': 2022,
                'subject': subjects['MED'],
                'topic': topics.get('MED_Pulmonology'),
                'difficulty': 'hard',
                'concept_tags': ['PE', 'pulmonary embolism', 'diagnosis', 'angiography'],
                'explanation': 'Conventional (catheter-based) pulmonary angiography remains the GOLD STANDARD for PE diagnosis. However, CTPA is the most commonly used first-line imaging due to its availability and non-invasive nature.',
                'mnemonic': 'Gold = old-school = Conventional angiography. CTPA = practical first choice.',
                'book_name': 'Harrison\'s Principles of Internal Medicine',
                'exam_source': 'UPSC CMS',
            },
            {
                'question_text': 'McBurney\'s point is located at:',
                'option_a': 'Junction of lateral 1/3 and medial 2/3 of a line from ASIS to umbilicus',
                'option_b': 'Junction of medial 1/3 and lateral 2/3 of a line from ASIS to umbilicus',
                'option_c': 'Midpoint of a line from ASIS to umbilicus',
                'option_d': 'Junction of upper 1/3 and lower 2/3 of a line from ASIS to umbilicus',
                'correct_answer': 'A',
                'year': 2021,
                'subject': subjects['SUR'],
                'topic': topics.get('SUR_General Surgery'),
                'difficulty': 'medium',
                'concept_tags': ['McBurney point', 'appendicitis', 'anatomy'],
                'explanation': 'McBurney\'s point lies at the junction of the lateral 1/3 and medial 2/3 of a line joining the right ASIS to the umbilicus. Tenderness here suggests acute appendicitis.',
                'mnemonic': 'McBurney = 1/3 from ASIS (lateral to medial). "1/3 from the Side"',
                'book_name': 'Bailey & Love\'s Short Practice of Surgery',
                'exam_source': 'UPSC CMS',
            },
            {
                'question_text': 'Partograph is used for monitoring:',
                'option_a': 'Antenatal care',
                'option_b': 'Progress of labor',
                'option_c': 'Postpartum period',
                'option_d': 'Neonatal assessment',
                'correct_answer': 'B',
                'year': 2020,
                'subject': subjects['OBG'],
                'topic': topics.get('OBG_Obstetrics - Normal'),
                'difficulty': 'easy',
                'concept_tags': ['partograph', 'labor monitoring', 'WHO'],
                'explanation': 'Partograph is a graphical record of the progress of labor. It plots cervical dilatation (alert & action lines), fetal heart rate, contractions, and maternal vitals against time.',
                'mnemonic': 'PARTograph = monitors PARTurition (labor)',
                'book_name': 'Shaw\'s Textbook of Gynecology',
                'exam_source': 'UPSC CMS',
            },
        ]

        created_count = 0
        for q_data in questions:
            q, created = Question.objects.get_or_create(
                question_text=q_data['question_text'],
                year=q_data['year'],
                defaults=q_data
            )
            if created:
                created_count += 1

        self.stdout.write(f'\n📝 Created {created_count} sample questions (total: {Question.objects.count()})')

        # Create some similar question mappings
        cardio_qs = Question.objects.filter(topic__name='Cardiology')
        nephro_qs = Question.objects.filter(topic__name='Nephrology')
        if cardio_qs.count() >= 2:
            q1, q2 = cardio_qs[:2]
            q1.similar_questions.add(q2)

        self.stdout.write(self.style.SUCCESS('\n✅ Seed data loaded successfully!'))
        self.stdout.write(f'\nSummary:')
        self.stdout.write(f'  Subjects: {Subject.objects.count()}')
        self.stdout.write(f'  Topics: {Topic.objects.count()}')
        self.stdout.write(f'  Questions: {Question.objects.count()}')
