"""Blog drafts generated from the question bank, no AI (manage.py generate_pyq_blog_drafts).

Two kinds, from the UPSC CMS papers in the bank (year, paper, display_number):

* one per paper: how its questions spread over the paper's sections, the topics they were tagged with, and every
  question (stem) in order;
* one per clinical term UPSC CMS asks often (``TERMS``, at least ``MIN_QUESTIONS`` questions): the questions that
  mention it, by year.

Only facts the bank holds (counts, years, numbers, the question stems). The answers are not in the drafts: the
question bank shows them by plan, and the drafts link to practice. Every draft is unpublished
(``is_published=False``) and says it was generated and is not reviewed; an editor reviews, edits and publishes it at
/admin/blog. A slug is created once (``GeneratedBlogDraft``): a draft an editor deleted is not created again.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from django.utils import timezone

MIN_QUESTIONS = 6
STEM_CHARS = 280
CATEGORY = 'PYQ Analysis'
SECTION_ORDER = ('General Medicine', 'Paediatrics', 'General Ability', 'General Surgery', 'Obstetrics & Gynaecology',
                 'Community Medicine')

# (label, slug, regex over the question stem): clinical terms; a stem matches on any of the patterns
TERMS = [
    ('Tuberculosis', 'tuberculosis', r'\btubercul|\bkoch|\bmdr[- ]?tb\b|\bntep\b|\brntcp\b|\bdots\b'),
    ('Diabetes mellitus', 'diabetes-mellitus', r'\bdiabet'),
    ('Hypertension', 'hypertension', r'\bhypertensi'),
    ('Thyroid disorders', 'thyroid-disorders', r'\bthyr|\bgraves\b|\bhashimoto'),
    ('Anaemia', 'anaemia', r'\ban(a)?emi'),
    ('Malaria', 'malaria', r'\bmalaria|\bplasmodi|\bartemisinin|\bchloroquine'),
    ('HIV and AIDS', 'hiv-aids', r'\bhiv\b|\baids\b|\bantiretroviral|\bart centre'),
    ('Hepatitis', 'hepatitis', r'\bhepatitis|\bhbsag|\bhbv\b|\bhcv\b'),
    ('Myocardial infarction', 'myocardial-infarction', r'\bmyocardial infarction|\bacute coronary|\bstemi\b|\bangina'),
    ('Heart failure', 'heart-failure', r'\bheart failure|\bcardiac failure|\bcongestive'),
    ('Asthma and COPD', 'asthma-copd', r'\basthma|\bcopd\b|\bchronic obstructive'),
    ('Pneumonia', 'pneumonia', r'\bpneumoni'),
    ('Meningitis and encephalitis', 'meningitis-encephalitis', r'\bmeningit|\bencephalit'),
    ('Stroke', 'stroke', r'\bstroke\b|\bcerebrovascular|\bhemipleg'),
    ('Epilepsy and seizures', 'epilepsy-seizures', r'\bepilep|\bseizure|\bconvuls'),
    ('Kidney failure', 'kidney-failure', r'\brenal failure|\bkidney injury|\bchronic kidney|\bdialysis|\buraemi|\buremi'),
    ('Nephrotic and nephritic syndrome', 'nephrotic-nephritic-syndrome', r'\bnephrotic|\bnephritic|\bglomerulonephrit'),
    ('Liver cirrhosis', 'liver-cirrhosis', r'\bcirrhos|\bportal hypertension|\bascites|\bvarices'),
    ('Pancreatitis', 'pancreatitis', r'\bpancreatit'),
    ('Peptic ulcer', 'peptic-ulcer', r'\bpeptic|\bduodenal ulcer|\bgastric ulcer|\bh\.? ?pylori'),
    ('Inflammatory bowel disease', 'inflammatory-bowel-disease', r'\bcrohn|\bulcerative colitis|\binflammatory bowel'),
    ('Appendicitis', 'appendicitis', r'\bappendic'),
    ('Intestinal obstruction', 'intestinal-obstruction', r'\bintestinal obstruction|\bvolvulus|\bintussuscept'),
    ('Hernia', 'hernia', r'\bhernia'),
    ('Breast cancer', 'breast-cancer', r'\bbreast (cancer|carcinoma|lump)|\bcarcinoma (of the )?breast|\bmastectomy'),
    ('Burns', 'burns', r'\bburns?\b'),
    ('Head injury', 'head-injury', r'\bhead injur|\bglasgow coma|\bextradural|\bsubdural'),
    ('Fractures', 'fractures', r'\bfractur'),
    ('Shock and sepsis', 'shock-sepsis', r'\bshock\b|\bsepsis|\bseptic'),
    ('Pre-eclampsia and eclampsia', 'pre-eclampsia-eclampsia', r'\beclamp|\bpre-?eclamp|\bpregnancy[- ]induced hypertension'),
    ('Postpartum haemorrhage', 'postpartum-haemorrhage', r'\bpost-?partum ha?emorrhage|\bpph\b'),
    ('Ectopic pregnancy', 'ectopic-pregnancy', r'\bectopic'),
    ('Placenta praevia and abruption', 'placenta-praevia-abruption', r'\bplacenta pra?evia|\babruptio|\bantepartum ha?emorrhage'),
    ('Contraception', 'contraception', r'\bcontracept|\biucd\b|\bcopper[- ]t\b|\boral pill|\bsterili[sz]ation'),
    ('Infertility', 'infertility', r'\binfertil'),
    ('Polycystic ovary syndrome', 'pcos', r'\bpolycystic ovar|\bpcos\b|\bpcod\b'),
    ('Cervical cancer', 'cervical-cancer', r'\bcarcinoma (of the )?cervix|\bcervical (cancer|carcinoma)|\bpap smear|\bhpv\b'),
    ('Ovarian tumours', 'ovarian-tumours', r'\bovarian (tumou?r|cancer|carcinoma|cyst|mass)'),
    ('Labour', 'labour', r'\blabou?r\b|\bpartograph'),
    ('Neonatal jaundice', 'neonatal-jaundice', r'\bneonatal jaundice|\bhyperbilirubin|\bkernicterus'),
    ('Diarrhoea and dehydration', 'diarrhoea-dehydration', r'\bdiarrho?ea|\bdehydrat|\bors\b|\boral rehydration'),
    ('Measles', 'measles', r'\bmeasles'),
    ('Immunisation', 'immunisation', r'\bvaccin|\bimmuni[sz]'),
    ('Malnutrition', 'malnutrition', r'\bmalnutrition|\bkwashiorkor|\bmarasmus|\bwasting\b|\bstunting'),
    ('Rickets and vitamin D', 'rickets-vitamin-d', r'\brickets|\bvitamin d\b'),
    ('Down syndrome', 'down-syndrome', r'\bdown(\'?s)? syndrome|\btrisomy 21'),
    ('Congenital heart disease', 'congenital-heart-disease', r'\bcongenital heart|\btetralogy|\bventricular septal|\batrial septal|\bpatent ductus'),
    ('Leprosy', 'leprosy', r'\bleprosy|\blepromatous|\bhansen'),
    ('Dengue', 'dengue', r'\bdengue'),
    ('Rabies', 'rabies', r'\brabies|\banimal bite|\bdog bite'),
    ('Cholera and typhoid', 'cholera-typhoid', r'\bcholera|\btyphoid|\benteric fever'),
    ('Filariasis', 'filariasis', r'\bfilari'),
    ('Biostatistics', 'biostatistics', r'\bsensitivity|\bspecificity|\bpredictive value|\bstandard deviation|\bmedian\b|\bp[- ]value|\bchi[- ]square'),
    ('Epidemiological studies', 'epidemiological-studies', r'\bcohort|\bcase[- ]control|\brandomi[sz]ed|\bincidence|\bprevalence'),
    ('National health programmes', 'national-health-programmes', r'\bnational .*programme|\bnhm\b|\bnrhm\b|\basha\b|\bjanani'),
    ('Water and sanitation', 'water-sanitation', r'\bchlorin|\bwater (purification|supply)|\bsanitation|\bsewage'),
    ('Occupational health', 'occupational-health', r'\boccupational|\bpneumoconios|\bsilicosis|\besi act\b|\bfactories act'),
    ('Poisoning', 'poisoning', r'\bpoison|\borganophosph|\bsnake ?bite|\bparacetamol overdose'),
    ('Leukaemia and lymphoma', 'leukaemia-lymphoma', r'\bleuka?emi|\blymphoma'),
    ('Haemoglobinopathies', 'haemoglobinopathies', r'\bsickle|\bthalass'),
    ('Rheumatoid arthritis and SLE', 'rheumatoid-arthritis-sle', r'\brheumatoid|\blupus|\bsle\b'),
    ('Skin infections and infestations', 'skin-infections', r'\bscabies|\bimpetigo|\btinea|\bpediculosis'),
    ('Psoriasis', 'psoriasis', r'\bpsoria'),
    ('Parkinson disease', 'parkinson-disease', r'\bparkinson'),
    ('Myasthenia gravis and GBS', 'myasthenia-gbs', r'\bmyasthenia|\bguillain|\bgbs\b'),
    ('Adrenal disorders', 'adrenal-disorders', r'\bcushing|\baddison|\bph(a)?eochromocytoma|\badrenal'),
    ('Electrolyte disorders', 'electrolyte-disorders', r'\bhypo(nat|kal|calc)|\bhyper(nat|kal|calc)'),
    ('ECG', 'ecg', r'\becg\b|\belectrocardiogra'),
    ('Arrhythmias', 'arrhythmias', r'\barrhythmi|\bfibrillation|\btachycardia|\bbradycardia|\bheart block'),
    ('Valvular heart disease', 'valvular-heart-disease', r'\bmitral|\baortic (stenosis|regurgitation)|\bvalv'),
    ('Rheumatic fever', 'rheumatic-fever', r'\brheumatic fever|\brheumatic heart'),
    ('Kidney stones', 'kidney-stones', r'\brenal (calcul|stone)|\burolithiasis|\bnephrolithiasis|\bureteric (stone|calcul)'),
    ('Prostate', 'prostate', r'\bprostat'),
    ('Thyroid swellings', 'thyroid-swellings', r'\bgoitre|\bthyroid (nodule|swelling|carcinoma|cancer)'),
    ('Varicose veins and DVT', 'varicose-veins-dvt', r'\bvaricose|\bdeep vein thrombosis|\bdvt\b'),
    ('Anaesthesia', 'anaesthesia', r'\ban(a)?esthe|\blocal an(a)?esthetic|\bmalignant hyperthermia'),
    ('Antenatal care', 'antenatal-care', r'\bantenatal|\bprenatal'),
    ('Menstrual disorders', 'menstrual-disorders', r'\bmenorrha|\bamenorrh|\bdysmenorrh|\bmenopaus'),
    ('Genetics', 'genetics', r'\bautosomal|\bx-linked|\bchromosom|\bkaryotyp'),
    ('Cataract', 'cataract', r'\bcataract'),
    ('Glaucoma', 'glaucoma', r'\bglaucoma|\bintraocular pressure'),
    ('Eye infections', 'eye-infections', r'\bconjunctivit|\btrachoma|\bkeratit|\bcorneal ulcer'),
    ('Ear disease', 'ear-disease', r'\botitis|\bmastoid|\bcholesteatoma|\bhearing loss|\bdeafness'),
    ('Nose and throat', 'nose-throat', r'\btonsil|\badenoid|\bsinusit|\bepistaxis|\blaryn'),
    ('Bone and joint infections', 'bone-joint-infections', r'\bosteomyelit|\bseptic arthritis'),
    ('Osteoporosis and osteoarthritis', 'osteoporosis-osteoarthritis', r'\bosteopor|\bosteoarthrit'),
    ('Spinal injury', 'spinal-injury', r'\bspinal (cord )?injur|\bparapleg|\bcauda equina'),
    ('Dislocations', 'dislocations', r'\bdislocat'),
    ('Gallstones', 'gallstones', r'\bgall ?(stone|bladder)|\bcholecyst|\bcholelith|\bcholangit'),
    ('Obstructive jaundice', 'obstructive-jaundice', r'\bobstructive jaundice|\bcholestat|\bperiampullary|\bcarcinoma (of the )?(head of )?(the )?pancreas'),
    ('Oesophagus', 'oesophagus', r'\bo?esophag|\bdysphagia|\bachalasia'),
    ('Colorectal cancer', 'colorectal-cancer', r'\bcolorectal|\bcarcinoma (of the )?(colon|rectum)|\bcolonic carcinoma'),
    ('Stomach cancer', 'stomach-cancer', r'\bcarcinoma (of the )?stomach|\bgastric (cancer|carcinoma)'),
    ('Anorectal disorders', 'anorectal-disorders', r'\bha?emorrhoid|\bfissure in ano|\banal fissure|\bfistula in ano|\bpilonidal'),
    ('Testis and scrotum', 'testis-scrotum', r'\btesticul|\btestis|\bhydrocele|\bvaricocele|\bundescended'),
    ('Wound healing and surgical infections', 'wound-healing', r'\bwound|\bsurgical site infection|\bkeloid|\babscess'),
    ('Blood transfusion', 'blood-transfusion', r'\btransfusion|\bblood group'),
    ('Vitamin deficiencies', 'vitamin-deficiencies', r'\bvitamin (a|b|c|k|b12|b1)\b|\bscurvy|\bberiberi|\bpellagra|\bfolic'),
    ('Iodine deficiency', 'iodine-deficiency', r'\biodine|\biodi[sz]ed salt'),
    ('Growth and development', 'growth-development', r'\bmilestone|\bgrowth chart|\bdevelopmental'),
    ('Breastfeeding', 'breastfeeding', r'\bbreast ?feed|\bbreast milk|\blactation'),
    ('Newborn care', 'newborn-care', r'\bneonat|\bnewborn|\bapgar|\bpreterm|\blow birth weight'),
    ('Pituitary disorders', 'pituitary-disorders', r'\bpituitar|\bacromegal|\bprolactin|\bdiabetes insipidus|\bsiadh\b'),
    ('Calcium and parathyroid', 'parathyroid', r'\bparathyroid|\bhypercalc|\bhypocalc'),
    ('Pleural disease', 'pleural-disease', r'\bpleural effusion|\bpneumothorax|\bempyema'),
    ('Lung cancer', 'lung-cancer', r'\blung (cancer|carcinoma)|\bbronchogenic'),
    ('Infective endocarditis', 'infective-endocarditis', r'\bendocardit'),
    ('Cardiomyopathy and pericarditis', 'cardiomyopathy-pericarditis', r'\bcardiomyopath|\bpericard'),
    ('Gastrointestinal bleeding', 'gi-bleeding', r'\bha?ematemesis|\bmela?ena|\bgastrointestinal bleed'),
    ('Coeliac disease and malabsorption', 'coeliac-malabsorption', r'\bc(o)?eliac|\bmalabsorption|\bsprue'),
    ('Leptospirosis and scrub typhus', 'leptospirosis-scrub-typhus', r'\bleptospir|\bscrub typhus|\brickettsi'),
    ('COVID-19', 'covid-19', r'\bcovid|\bsars-?cov'),
    ('Depression and psychosis', 'depression-psychosis', r'\bdepressi|\bschizophren|\bpsychos|\bbipolar|\bsuicid'),
    ('Alcohol and substance use', 'alcohol-substance-use', r'\balcohol|\bopioid|\bsubstance (use|abuse)|\bdelirium tremens'),
    ('Antibiotics', 'antibiotics', r'\bantibiotic|\bpenicillin|\bcephalosporin|\bvancomycin|\bmacrolide'),
    ('Infant and maternal mortality', 'infant-maternal-mortality', r'\binfant mortality|\bmaternal mortality|\bperinatal mortality|\bimr\b'),
    ('Screening and surveillance', 'screening-surveillance', r'\bscreening|\bsurveillance|\bnotifiab'),
    ('Health education and communication', 'health-communication', r'\bhealth education|\bcommunication|\bcounsell'),
    ('Nutrition programmes', 'nutrition-programmes', r'\bicds\b|\bmid-?day meal|\banganwadi|\bsupplementary nutrition'),
    ('Biomedical waste and disasters', 'biomedical-waste-disasters', r'\bbio-?medical waste|\bhospital waste|\bdisaster|\btriage'),
    ('Demography', 'demography', r'\bbirth rate|\bdeath rate|\bfertility rate|\bdependency ratio|\bcensus|\bpopulation pyramid'),
]


@dataclass
class Draft:
    slug: str
    kind: str
    title: str
    description: str
    excerpt: str
    subcategory: str
    tags: list
    body: str
    faqs: list = field(default_factory=list)


def _stem(text) -> str:
    text = ' '.join(str(text or '').replace('|', ' ').split())
    return text if len(text) <= STEM_CHARS else text[:STEM_CHARS - 1].rstrip() + '…'


def _roman(paper) -> str:
    return 'I' if paper == 1 else 'II'


def _papers():
    """{(year, paper): [questions in order]} of the dated UPSC CMS papers in the bank."""
    from questions.models import Question

    papers = defaultdict(list)
    qs = (Question.objects.filter(exam_type='cms', is_active=True, year__gte=2000, paper__in=[1, 2],
                                  display_number__isnull=False)
          .select_related('subject', 'topic').order_by('year', 'paper', 'display_number'))
    for q in qs:
        papers[(q.year, q.paper)].append(q)
    return papers


def _key_note(year) -> str:
    if year >= 2026:
        return ('UPSC has not published the official answer key of this paper yet, so the answers in the question bank '
                'are not official.')
    return 'The answers in the question bank follow the official UPSC answer key of this paper.'


def paper_draft(year, paper, questions) -> Draft:
    sections = defaultdict(list)
    for q in questions:
        sections[getattr(q.subject, 'name', '') or 'Other'].append(q)
    order = sorted(sections, key=lambda s: (SECTION_ORDER.index(s) if s in SECTION_ORDER else 99, s))
    n = len(questions)
    title = f'UPSC CMS {year} Paper {_roman(paper)}: section-wise analysis and every question'
    lines = [
        f'UPSC CMS {year} Paper {_roman(paper)} had **{n} questions**: '
        + ', '.join(f'{s} ({len(sections[s])})' for s in order) + '. '
        'This page shows how they were spread over the sections and topics, then lists every question in the order '
        'of the paper, so you can see what UPSC asked and practise the paper in the question bank.',
        '',
        f'> Generated from the CrackCMS question bank on {timezone.localdate():%d %B %Y}; not reviewed yet. '
        f'{_key_note(year)}',
        '',
        '## Section-wise breakdown',
        '',
        '| Section | Questions | Question numbers |',
        '|---|---|---|',
    ]
    for s in order:
        nums = [q.display_number for q in sections[s]]
        lines.append(f'| {s} | {len(nums)} | {min(nums)}–{max(nums)} |')
    topics_by_section = []
    for s in order:
        counts = Counter(q.topic.name for q in sections[s] if q.topic_id and q.topic.name not in ('General', ''))
        if counts:
            listed = ', '.join(f'{name} ({c})' for name, c in counts.most_common(12))
            topics_by_section.append(f'- **{s}:** {listed}')
    if topics_by_section:
        lines += ['', '## Topics tested', '', 'The most frequent topics the questions are tagged with:', '',
                  *topics_by_section]
    lines += ['', '## Every question', '']
    for s in order:
        nums = [q.display_number for q in sections[s]]
        lines += [f'### {s} (Q{min(nums)}–{max(nums)})', '']
        lines += [f'{q.display_number}. {_stem(q.question_text)}' for q in sections[s]]
        lines.append('')
    lines += ['## Practise this paper', '',
              'Answer these questions with explanations in the [question bank](/practice), or take the full paper '
              'under exam conditions in the [PYQ simulator](/simulator).']
    faqs = [
        {'q': f'How many questions were in UPSC CMS {year} Paper {_roman(paper)}?',
         'a': f'{n} questions: ' + ', '.join(f'{s} {len(sections[s])}' for s in order) + '.'},
        {'q': 'Is there negative marking in UPSC CMS?',
         'a': 'Yes: one third of the marks of a question is deducted for each wrong answer.'},
        {'q': f'Where are the answers to UPSC CMS {year} Paper {_roman(paper)}?',
         'a': 'In the CrackCMS question bank and PYQ simulator, with explanations. ' + _key_note(year)},
    ]
    return Draft(
        slug=f'upsc-cms-{year}-paper-{_roman(paper).lower()}-analysis', kind='paper', title=title,
        description=(f'UPSC CMS {year} Paper {_roman(paper)}: {n} questions by section and topic, and every question '
                     f'of the paper in order, from the CrackCMS question bank.'),
        excerpt=f'How the {n} questions of UPSC CMS {year} Paper {_roman(paper)} were spread over the sections, with every question.',
        subcategory='Paper analysis', tags=['UPSC CMS', 'PYQ', str(year), f'Paper {_roman(paper)}'],
        body='\n'.join(lines), faqs=faqs)


def term_draft(label, slug, matches) -> Draft:
    by_year = defaultdict(list)
    for q in matches:
        by_year[q.year].append(q)
    years = sorted(by_year)
    n = len(matches)
    span = f'{years[0]}–{years[-1]}' if len(years) > 1 else str(years[0])
    lines = [
        f'UPSC CMS asked **{n} questions** that mention {label.lower()} in the papers from {span} in the CrackCMS '
        f'question bank. They are listed below by year, with the paper and the question number, so you can see what '
        f'UPSC asks about {label.lower()} and practise them.',
        '',
        f'> Generated from the CrackCMS question bank on {timezone.localdate():%d %B %Y}; not reviewed yet. A question '
        'is listed when its text mentions the topic. The answers and explanations are in the question bank.',
        '',
        '## How often it is asked',
        '',
        '| Year | Questions |',
        '|---|---|',
        *[f'| {y} | {len(by_year[y])} |' for y in reversed(years)],
        '',
        '## The questions',
        '',
    ]
    for y in reversed(years):
        lines += [f'### {y}', '']
        lines += [f'- **Paper {_roman(q.paper)}, Q{q.display_number}.** {_stem(q.question_text)}'
                  for q in sorted(by_year[y], key=lambda q: (q.paper, q.display_number))]
        lines.append('')
    lines += ['## Practise them', '',
              'Answer these questions with explanations in the [question bank](/practice), or take whole papers in '
              'the [PYQ simulator](/simulator).']
    top = sorted(years, key=lambda y: (-len(by_year[y]), -y))[:3]
    faqs = [
        {'q': f'How many UPSC CMS questions mention {label.lower()}?',
         'a': f'{n} questions in the papers from {span} in the CrackCMS question bank.'},
        {'q': f'In which years did UPSC CMS ask most about {label.lower()}?',
         'a': ', '.join(f'{y} ({len(by_year[y])})' for y in top) + '.'},
    ]
    return Draft(
        slug=f'upsc-cms-pyqs-{slug}', kind='term',
        title=f'UPSC CMS previous year questions on {label} ({span})',
        description=f'All {n} UPSC CMS questions from {span} that mention {label.lower()}, by year, from the CrackCMS question bank.',
        excerpt=f'{n} UPSC CMS questions on {label.lower()} ({span}), listed by year with paper and question number.',
        subcategory='Topic-wise PYQs', tags=['UPSC CMS', 'PYQ', label], body='\n'.join(lines), faqs=faqs)


def build_drafts(min_questions=MIN_QUESTIONS) -> list[Draft]:
    """Paper drafts for the papers with at least 100 questions; topic drafts for the terms with at least
    ``min_questions`` questions and a body that is not thin (blog_engine.text_stats.THIN_POST_WORDS)."""
    from blog_engine.text_stats import THIN_POST_WORDS, count_words

    papers = _papers()
    drafts = [paper_draft(year, paper, qs) for (year, paper), qs in sorted(papers.items()) if len(qs) >= 100]
    every = [q for qs in papers.values() for q in qs]
    for label, slug, pattern in TERMS:
        rx = re.compile(pattern, re.I)
        matches = [q for q in every if rx.search(q.question_text or '')]
        if len(matches) >= min_questions:
            draft = term_draft(label, slug, matches)
            if count_words(draft.body) >= THIN_POST_WORDS:
                drafts.append(draft)
    return drafts


def save_drafts(drafts, *, apply) -> Counter:
    """Create the drafts whose slug was never created before (no post, no ledger row)."""
    from blog_engine.models import BlogPost, GeneratedBlogDraft

    stats = Counter()
    today = timezone.localdate().isoformat()
    for draft in drafts:
        if GeneratedBlogDraft.objects.filter(slug=draft.slug).exists():
            stats['already generated once'] += 1
            continue
        if BlogPost.objects.filter(slug=draft.slug).exists():
            stats['a post has this slug'] += 1
            continue
        stats[f'new {draft.kind} draft'] += 1
        if not apply:
            continue
        BlogPost.objects.create(
            slug=draft.slug, title=draft.title, description=draft.description, excerpt=draft.excerpt,
            category=CATEGORY, subcategory=draft.subcategory, tags=draft.tags, difficulty='intermediate',
            author_id='crackcms-editorial', reviewed_by='', author='CrackCMS Editorial Team',
            author_role='Draft generated from the question bank (to be reviewed)', date_published=today,
            date_modified=today, updated_at=today, primary_cta={'label': 'Practise UPSC CMS PYQs', 'href': '/practice'},
            related_exam_paths=['/cms'], faqs=draft.faqs, toc=[], references=[],
            revision_log=[{'date': today, 'note': 'Draft generated from the CrackCMS question bank '
                                                  '(generate_pyq_blog_drafts); not reviewed'}],
            body=draft.body, is_published=False)
        GeneratedBlogDraft.objects.create(slug=draft.slug, kind=draft.kind)
    return stats
