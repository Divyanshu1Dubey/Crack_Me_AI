"""
UPSC CMS (Combined Medical Services) Comprehensive Knowledge Base

This module provides structured knowledge about the UPSC CMS examination
to be used by the AI system for better question answering, analysis, and guidance.
"""

# UPSC CMS Exam Pattern & Structure
EXAM_PATTERN = {
    "name": "UPSC Combined Medical Services (CMS) Examination",
    "conducting_body": "Union Public Service Commission (UPSC)",
    "frequency": "Annual",
    "stages": [
        "Written Examination (Objective Type)",
        "Personality Test / Interview"
    ],
    "papers": {
        "Paper I": {
            "name": "General Ability & General Medicine",
            "marks": 250,
            "duration": "2 hours",
            "parts": {
                "Part A": {
                    "name": "General Ability",
                    "marks": 60,
                    "subjects": [
                        "General Knowledge (30 marks)",
                        "English Language (30 marks)"
                    ]
                },
                "Part B": {
                    "name": "Professional Subjects",
                    "marks": 190,
                    "subjects": [
                        "General Medicine (95 marks)",
                        "Paediatrics (47.5 marks)",
                        "Dermatology (23.75 marks)",
                        "Psychiatry (23.75 marks)"
                    ]
                }
            }
        },
        "Paper II": {
            "name": "Surgical Disciplines & Preventive Medicine",
            "marks": 250,
            "duration": "2 hours",
            "parts": {
                "Part A": {
                    "name": "Surgical Subjects",
                    "marks": 120,
                    "subjects": [
                        "General Surgery (45 marks)",
                        "Orthopaedics (15 marks)",
                        "Anaesthesia (15 marks)",
                        "Ophthalmology (15 marks)",
                        "ENT (15 marks)",
                        "Radiodiagnosis (15 marks)"
                    ]
                },
                "Part B": {
                    "name": "Obstetrics & Gynaecology + PSM",
                    "marks": 130,
                    "subjects": [
                        "Obstetrics & Gynaecology (65 marks)",
                        "Preventive & Social Medicine (65 marks)"
                    ]
                }
            }
        }
    },
    "marking_scheme": {
        "per_question_marks": 1,
        "negative_marking": "1/3 of marks for wrong answer",
        "no_negative_for_unattempted": True
    },
    "qualifying_marks": {
        "general": "Minimum 40% in each paper",
        "reserved_categories": "Minimum 35% in each paper"
    },
    "interview_marks": 100,
    "total_marks": 600
}

# Subject-wise Important Topics
HIGH_YIELD_TOPICS = {
    "General Medicine": {
        "weight": "Very High (38%)",
        "topics": [
            "Cardiology (MI, Heart Failure, Arrhythmias, Valvular diseases)",
            "Neurology (Stroke, Epilepsy, Parkinson's, Myasthenia)",
            "Nephrology (AKI, CKD, Glomerulonephritis, Dialysis)",
            "Respiratory (COPD, Asthma, Pneumonia, TB, ARDS)",
            "Gastroenterology (Liver cirrhosis, IBD, Pancreatitis)",
            "Endocrinology (DM, Thyroid disorders, Adrenal diseases)",
            "Hematology (Anemia, Leukemia, Bleeding disorders)",
            "Infectious Diseases (HIV, Dengue, Malaria, COVID-19)",
            "Rheumatology (RA, SLE, Vasculitis)",
            "Poisoning and Emergency Medicine"
        ],
        "standard_textbooks": [
            "Harrison's Principles of Internal Medicine (Gold Standard)",
            "API Textbook of Medicine",
            "Davidson's Principles and Practice of Medicine"
        ]
    },
    "Paediatrics": {
        "weight": "High (19%)",
        "topics": [
            "Neonatology (Birth asphyxia, RDS, NNJ, Sepsis)",
            "Growth & Development milestones",
            "National Immunization Schedule",
            "Pediatric Infections (Measles, Pertussis, Diphtheria)",
            "Congenital Heart Diseases",
            "Pediatric Neurology",
            "Nutritional disorders (PEM, Rickets, Scurvy)",
            "Genetic disorders",
            "Pediatric Emergencies"
        ],
        "standard_textbooks": [
            "Ghai Essential Pediatrics (Most important)",
            "Nelson Textbook of Pediatrics",
            "OP Ghai Essential Pediatrics"
        ]
    },
    "PSM (Preventive & Social Medicine)": {
        "weight": "High (26%)",
        "topics": [
            "Epidemiology (Study designs, Biostatistics)",
            "National Health Programs",
            "Demography & Family Planning",
            "Nutrition & Health",
            "Communicable Disease Control",
            "Non-communicable Disease Control",
            "Environmental Health",
            "Occupational Health",
            "Health Care Delivery System in India",
            "Maternal & Child Health Programs",
            "Biomedical Waste Management"
        ],
        "standard_textbooks": [
            "Park's Textbook of Preventive & Social Medicine (Bible of PSM)",
            "K. Park PSM"
        ]
    },
    "Obstetrics & Gynaecology": {
        "weight": "High (26%)",
        "topics": [
            "Normal & High-risk Pregnancy",
            "Labor & Delivery",
            "PPH & Complications of Pregnancy",
            "Contraception methods",
            "Menstrual disorders",
            "Infertility",
            "Gynecological cancers",
            "PCOS & Endometriosis",
            "Medical Termination of Pregnancy",
            "Maternal mortality causes"
        ],
        "standard_textbooks": [
            "DC Dutta's Textbook of Obstetrics",
            "Shaw's Textbook of Gynaecology",
            "Jeffcoate's Principles of Gynaecology"
        ]
    },
    "General Surgery": {
        "weight": "High (18%)",
        "topics": [
            "Wound healing & Surgical infections",
            "Shock & Fluid management",
            "Hernia (Inguinal, Femoral, Ventral)",
            "Thyroid & Breast diseases",
            "GI Surgery (Appendicitis, Cholecystitis, Intestinal Obstruction)",
            "Vascular surgery basics",
            "Surgical Oncology basics",
            "Trauma & Burns",
            "Pre & Post operative care"
        ],
        "standard_textbooks": [
            "Bailey & Love's Short Practice of Surgery",
            "SRB's Manual of Surgery",
            "Sabiston Textbook of Surgery"
        ]
    },
    "Psychiatry": {
        "weight": "Medium (9.5%)",
        "topics": [
            "Schizophrenia & Psychotic disorders",
            "Mood disorders (Depression, Bipolar)",
            "Anxiety disorders",
            "Substance abuse & Deaddiction",
            "Childhood psychiatric disorders",
            "Psychopharmacology",
            "Mental Health Act",
            "Emergency Psychiatry"
        ],
        "standard_textbooks": [
            "Ahuja's A Short Textbook of Psychiatry",
            "Kaplan & Sadock's Synopsis of Psychiatry"
        ]
    },
    "Dermatology": {
        "weight": "Medium (9.5%)",
        "topics": [
            "Infectious skin diseases (Leprosy, Fungal infections)",
            "Autoimmune skin diseases (Pemphigus, Bullous pemphigoid)",
            "Psoriasis & Eczema",
            "Drug reactions (SJS, TEN, DRESS)",
            "STDs & HIV skin manifestations",
            "Skin tumors",
            "Topical therapy basics"
        ],
        "standard_textbooks": [
            "IADVL Textbook of Dermatology",
            "Roxburgh's Common Skin Diseases"
        ]
    },
    "Ophthalmology": {
        "weight": "Medium (6%)",
        "topics": [
            "Cataract & its management",
            "Glaucoma types & treatment",
            "Refractive errors",
            "Corneal diseases",
            "Retinal diseases (Diabetic retinopathy)",
            "Squint & Amblyopia",
            "Eye injuries",
            "National programs for blindness"
        ],
        "standard_textbooks": [
            "Khurana Ophthalmology",
            "Parson's Diseases of the Eye"
        ]
    },
    "ENT": {
        "weight": "Medium (6%)",
        "topics": [
            "Otitis media & complications",
            "Hearing loss (types, assessment)",
            "Rhinosinusitis",
            "Epistaxis causes & management",
            "Tonsillitis & Adenoids",
            "Laryngeal tumors",
            "Foreign body in airway/esophagus",
            "Vertigo & balance disorders"
        ],
        "standard_textbooks": [
            "Dhingra ENT",
            "Logan Turner's Diseases of Nose, Throat and Ear"
        ]
    },
    "Orthopaedics": {
        "weight": "Medium (6%)",
        "topics": [
            "Fracture types & healing",
            "Common fractures (Colles, Hip, Spinal)",
            "Joint disorders (OA, RA, Gout)",
            "Bone tumors",
            "Congenital abnormalities",
            "Spinal disorders",
            "Sports injuries"
        ],
        "standard_textbooks": [
            "Maheshwari's Essential Orthopaedics",
            "Apley's System of Orthopaedics"
        ]
    },
    "Anaesthesia": {
        "weight": "Medium (6%)",
        "topics": [
            "Pre-anesthetic evaluation",
            "General anaesthesia agents",
            "Regional anaesthesia (Spinal, Epidural)",
            "Airway management",
            "Monitoring during anaesthesia",
            "Post-operative complications",
            "CPR & Basic Life Support",
            "Anaphylaxis management"
        ],
        "standard_textbooks": [
            "Aitkenhead's Textbook of Anaesthesia",
            "Lee's Synopsis of Anaesthesia"
        ]
    },
    "Radiodiagnosis": {
        "weight": "Medium (6%)",
        "topics": [
            "X-ray physics & safety",
            "Chest X-ray interpretation",
            "Abdominal imaging",
            "CT & MRI basics",
            "USG basics & applications",
            "Common radiological signs",
            "Contrast media & reactions"
        ],
        "standard_textbooks": [
            "Radiodiagnosis by Satish K. Bhargava",
            "Textbook of Radiology by David Sutton"
        ]
    }
}

# Important National Health Programs
NATIONAL_HEALTH_PROGRAMS = {
    "Communicable Diseases": [
        {"name": "National Tuberculosis Elimination Programme (NTEP)", "target_year": 2025},
        {"name": "National Vector Borne Disease Control Programme (NVBDCP)", "diseases": ["Malaria", "Dengue", "Chikungunya", "JE", "Kala-azar", "Filariasis"]},
        {"name": "National AIDS Control Programme (NACP)", "current_phase": "Phase V"},
        {"name": "National Leprosy Eradication Programme (NLEP)", "elimination_target": "<1/10000},
        {"name": "Revised National TB Control Programme", "strategy": "DOTS plus"},
        {"name": "Universal Immunization Programme (UIP)", "vaccines": ["BCG", "OPV", "DPT", "Hepatitis B", "Measles", "JE", "Rotavirus", "PCV", "IPV"]},
    ],
    "Non-communicable Diseases": [
        {"name": "National Programme for Prevention and Control of Cancer, Diabetes, CVD and Stroke (NPCDCS)"},
        {"name": "National Mental Health Programme (NMHP)"},
        {"name": "National Programme for Prevention and Control of Deafness (NPPCD)"},
        {"name": "National Programme for Control of Blindness (NPCB)", "vision": "VISION 2020"},
    ],
    "Maternal & Child Health": [
        {"name": "Janani Suraksha Yojana (JSY)", "incentives": "Institutional delivery"},
        {"name": "Janani Shishu Suraksha Karyakram (JSSK)", "services": "Free delivery, C-section, treatment"},
        {"name": "ICDS (Integrated Child Development Services)"},
        {"name": "Rashtriya Bal Swasthya Karyakram (RBSK)", "screening": "4Ds - Defects, Diseases, Deficiencies, Development delays"},
        {"name": "Rashtriya Kishor Swasthya Karyakram (RKSK)", "focus": "Adolescent health"},
        {"name": "Mission Indradhanush", "goal": "Full immunization all children"},
        {"name": "LaQshya", "focus": "Quality Labor Room & Maternity OT"},
    ],
    "Nutrition": [
        {"name": "National Nutrition Mission (POSHAN Abhiyaan)", "targets": ["Reduce stunting", "Reduce undernutrition", "Reduce anemia"]},
        {"name": "Mid Day Meal Scheme"},
        {"name": "National Iodine Deficiency Disorders Control Programme (NIDDCP)"},
    ],
    "Others": [
        {"name": "Ayushman Bharat", "components": ["Health & Wellness Centres", "PM-JAY"]},
        {"name": "National Health Mission (NHM)", "components": ["NRHM", "NUHM"]},
        {"name": "National Organ Transplant Programme"},
    ]
}

# Drugs of Choice for Common Conditions
DRUGS_OF_CHOICE = {
    "Infections": {
        "Typhoid": "Ceftriaxone / Azithromycin",
        "Tuberculosis": "HRZE (Isoniazid, Rifampicin, Pyrazinamide, Ethambutol)",
        "Malaria_P_vivax": "Chloroquine + Primaquine",
        "Malaria_P_falciparum": "Artemisinin-based Combination Therapy (ACT)",
        "Meningitis_bacterial": "Ceftriaxone",
        "UTI_uncomplicated": "Nitrofurantoin / Fosfomycin",
        "Pneumonia_community": "Amoxicillin + Clavulanate / Azithromycin",
        "Leprosy_PB": "Rifampicin + Dapsone (6 months)",
        "Leprosy_MB": "Rifampicin + Dapsone + Clofazimine (12 months)",
    },
    "Cardiology": {
        "Hypertension_first_line": "ACE inhibitors / ARBs / CCBs / Thiazides",
        "Heart_failure": "ACE inhibitor + Beta blocker + Diuretic",
        "MI_acute": "Aspirin + Clopidogrel + Heparin + Statin",
        "Atrial_fibrillation": "Rate control: Beta blockers, Rhythm: Amiodarone",
    },
    "Endocrine": {
        "Type2_DM_first_line": "Metformin",
        "Hypothyroidism": "Levothyroxine",
        "Hyperthyroidism": "Carbimazole/Methimazole or Propylthiouracil",
        "Addisons_crisis": "IV Hydrocortisone",
    },
    "Neurology": {
        "Epilepsy_focal": "Carbamazepine / Levetiracetam",
        "Epilepsy_generalized": "Valproate / Levetiracetam",
        "Status_epilepticus": "IV Lorazepam → IV Phenytoin → Levetiracetam",
        "Parkinsons": "Levodopa + Carbidopa",
        "Migraine_acute": "NSAIDs / Triptans",
        "Migraine_prophylaxis": "Propranolol / Topiramate",
    },
    "Psychiatry": {
        "Schizophrenia": "Risperidone / Olanzapine",
        "Depression": "SSRIs (Fluoxetine, Sertraline)",
        "Bipolar_acute_mania": "Lithium / Valproate",
        "Anxiety": "SSRIs / Benzodiazepines (short term)",
        "OCD": "Fluoxetine / Fluvoxamine (high dose)",
    },
}

# Common Clinical Signs & Their Significance
CLINICAL_SIGNS = {
    "Nephrology": {
        "Nephrotic_syndrome": ["Proteinuria >3.5g/day", "Hypoalbuminemia", "Edema", "Hyperlipidemia"],
        "Nephritic_syndrome": ["Hematuria", "Oliguria", "Hypertension", "Mild proteinuria"],
    },
    "Neurology": {
        "UMN_lesion": ["Spasticity", "Hyperreflexia", "Positive Babinski", "Clonus", "No muscle wasting"],
        "LMN_lesion": ["Flaccidity", "Areflexia", "Muscle wasting", "Fasciculations"],
    },
    "Cardiology": {
        "Left_heart_failure": ["Dyspnea", "Orthopnea", "PND", "Pulmonary edema"],
        "Right_heart_failure": ["JVP elevation", "Hepatomegaly", "Pedal edema", "Ascites"],
    },
}

# Important Medical Laws & Acts
MEDICAL_LAWS = [
    {"name": "Mental Healthcare Act 2017", "key_points": ["Advance directive", "Right to access healthcare", "Decriminalized suicide attempt"]},
    {"name": "Medical Termination of Pregnancy Act 2021", "amendments": ["Upper limit 24 weeks for special categories", "Opinion of one doctor up to 20 weeks"]},
    {"name": "PCPNDT Act 1994", "purpose": "Prohibition of sex selection"},
    {"name": "Transplantation of Human Organs Act 1994", "covers": "Organ donation & transplantation regulation"},
    {"name": "Clinical Establishments Act 2010", "purpose": "Registration & regulation of clinical establishments"},
    {"name": "Consumer Protection Act 2019", "medical_relevance": "Medical negligence cases"},
    {"name": "National Medical Commission Act 2019", "replaced": "Medical Council of India"},
]

# Important Vaccines & Schedule
IMMUNIZATION_SCHEDULE = {
    "Birth": ["BCG", "OPV-0", "Hepatitis B - Birth dose"],
    "6_weeks": ["OPV-1", "Pentavalent-1", "Rotavirus-1", "fIPV-1", "PCV-1"],
    "10_weeks": ["OPV-2", "Pentavalent-2", "Rotavirus-2"],
    "14_weeks": ["OPV-3", "Pentavalent-3", "Rotavirus-3", "fIPV-2", "PCV-2"],
    "9_months": ["MR-1", "JE-1", "PCV-Booster", "Vitamin A - 1st dose"],
    "16-24_months": ["MR-2", "JE-2", "DPT Booster-1", "OPV Booster", "Vitamin A - 2nd dose"],
    "5-6_years": ["DPT Booster-2"],
    "10_years": ["TT-1"],
    "16_years": ["TT-2"],
    "Pregnant_women": ["Td-1 (early)", "Td-2 (after 4 weeks)", "Td-Booster (if needed)"],
}

def get_topic_importance(subject: str, topic: str) -> dict:
    """Get importance level and study tips for a topic."""
    if subject in HIGH_YIELD_TOPICS:
        subject_data = HIGH_YIELD_TOPICS[subject]
        if topic in subject_data.get("topics", []):
            return {
                "importance": "High Yield",
                "subject_weight": subject_data["weight"],
                "textbooks": subject_data["standard_textbooks"]
            }
    return {"importance": "Standard", "subject_weight": "Unknown", "textbooks": []}


def get_study_advice(subject: str) -> dict:
    """Get study advice for a subject."""
    if subject in HIGH_YIELD_TOPICS:
        data = HIGH_YIELD_TOPICS[subject]
        return {
            "subject": subject,
            "weightage": data["weight"],
            "key_topics": data["topics"][:5],  # Top 5
            "recommended_books": data["standard_textbooks"],
            "tip": f"Focus on {data['topics'][0]} first as it's most commonly asked."
        }
    return {"error": "Subject not found"}


def get_exam_info() -> dict:
    """Get complete exam pattern information."""
    return EXAM_PATTERN


def search_drug_of_choice(condition: str) -> str:
    """Search for drug of choice for a condition."""
    condition_lower = condition.lower()
    for category, drugs in DRUGS_OF_CHOICE.items():
        for cond, drug in drugs.items():
            if condition_lower in cond.lower():
                return f"{cond}: {drug}"
    return "Drug of choice not found in database"


# Export all for use in AI system
__all__ = [
    'EXAM_PATTERN',
    'HIGH_YIELD_TOPICS',
    'NATIONAL_HEALTH_PROGRAMS',
    'DRUGS_OF_CHOICE',
    'CLINICAL_SIGNS',
    'MEDICAL_LAWS',
    'IMMUNIZATION_SCHEDULE',
    'get_topic_importance',
    'get_study_advice',
    'get_exam_info',
    'search_drug_of_choice',
]
