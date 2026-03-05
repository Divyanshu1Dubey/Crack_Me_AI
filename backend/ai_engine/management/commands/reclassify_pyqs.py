import os
from django.core.management.base import BaseCommand
from questions.models import Subject, Question
import logging
import re

logger = logging.getLogger(__name__)

# Subject mapping based on CMS Syllabus
# Paper 1: General Medicine, Pediatrics
# Paper 2: Surgery, Gynaecology & Obstetrics, Preventive & Social Medicine

KEYWORDS = {
    "General Medicine": [r"medicine", r"ecg", r"heart", r"blood pressure", r"diabetes", r"hypertension", r"asthma", r"pneumonia", r"tuberculosis", r"fever", r"syndrome", r"infarction", r"arrhythmia"],
    "Pediatrics": [r"pediatric", r"child", r"infant", r"neonate", r"baby", r"birth", r"congenital", r"immunization", r"vaccine", r"growth", r"development", r"measles", r"polio"],
    "Surgery": [r"surgery", r"surgical", r"operation", r"incision", r"trauma", r"fracture", r"burn", r"hernia", r"appendicitis", r"ulcer", r"tumor", r"cancer", r"excision", r"laparotomy"],
    "Obstetrics & Gynecology": [r"obstetric", r"gynecology", r"pregnancy", r"maternal", r"fetal", r"uterus", r"ovary", r"menstruation", r"labor", r"delivery", r"postpartum", r"abortion", r"contraception", r"pcos", r"cervix"],
    "Preventive & Social Medicine": [r"preventive", r"social", r"community", r"epidemiology", r"public health", r"screening", r"prevalence", r"incidence", r"outbreak", r"endemic", r"epidemic", r"pandemic", r"sanitation", r"hygiene", r"who", r"naco", r"program"]
}

class Command(BaseCommand):
    help = 'Reclassify existing questions into proper subjects based on paper and text.'

    def handle(self, *args, **options):
        # Ensure subjects exist
        subjects = {}
        for subj_name in KEYWORDS.keys():
            subjects[subj_name], _ = Subject.objects.get_or_create(name=subj_name)
            
        questions = Question.objects.all()
        self.stdout.write(self.style.SUCCESS(f"Found {questions.count()} questions to reclassify."))
        
        updated_count = 0
        for q in questions:
            original_subject = q.subject
            new_subject = None
            
            # 1. Base classification on Paper
            if q.paper == 1:
                possible_subjects = ["General Medicine", "Pediatrics"]
            elif q.paper == 2:
                possible_subjects = ["Surgery", "Obstetrics & Gynecology", "Preventive & Social Medicine"]
            else:
                possible_subjects = list(KEYWORDS.keys())
                
            # 2. Refine classification with keywords
            text = q.question_text.lower()
            best_match = None
            max_matches = -1
            
            for subj_name in possible_subjects:
                matches = 0
                for pattern in KEYWORDS[subj_name]:
                    if re.search(pattern, text):
                        matches += 1
                if matches > max_matches:
                    max_matches = matches
                    best_match = subj_name
                    
            if best_match and max_matches > 0:
                new_subject = subjects[best_match]
            elif possible_subjects:
                # Fallback to the first possible subject if no keywords match securely
                new_subject = subjects[possible_subjects[0]]
                
            if new_subject and original_subject != new_subject:
                q.subject = new_subject
                q.save()
                updated_count += 1
                
        self.stdout.write(self.style.SUCCESS(f"Successfully reclassified {updated_count} questions!"))
