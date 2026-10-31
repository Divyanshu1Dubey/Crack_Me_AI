"""Audit of question subject tags (NEET PG mis-tagging + CMS placeholder subjects).

Run (from backend/):

    DJANGO_ENV_FILE=.env.localdev python -m ai_eval.subject_audit --out ../docs/audit/data_quality \
        --csv C:/Users/DIVYANSHU/crack_local/data_quality/subject_suggestions.csv [--apply-local]

What it does
* Trusted labels: NEET PG questions imported from per-subject PYQ compilations
  ("Medicine pyqs.pdf", "PSM pyqs.pdf", …) carry their subject in the source
  file name. Their current subject tags agree with that label only part of
  the time (they were assigned by a keyword heuristic).
* A TF-IDF + logistic-regression classifier is trained on the trusted set and
  evaluated with 5-fold stratified cross-validation (one copy per stem, so
  duplicates cannot leak across folds). Metrics are reported as measured.
* Suggestions: trusted questions whose tag disagrees with their source label
  (method=source_file), and questions with no subject-wise source (full
  papers, blank source) or a placeholder CMS subject (method=classifier, with
  the model's probability).
* --apply-local (refused unless settings.DEBUG) rewrites ONLY the
  source_file suggestions in the local database. Classifier suggestions are
  for human review; nothing here touches production.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict

if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')
    import django
    django.setup()

from django.conf import settings  # noqa: E402

from ai_engine.lexical_index import fold  # noqa: E402

SOURCE_KEYWORDS = [  # (pattern in source file name, subject code)
    (r'\bmedicine\b', 'MED'), (r'\bbiochem', 'BCH'), (r'\banatomy\b', 'ANA'), (r'\bobg\b|\bobs', 'OBG'),
    (r'\bpharm', 'PHM'), (r'\bderma', 'DER'), (r'\bpsm\b|community', 'PSM'), (r'\bmicro', 'MIC'),
    (r'\bfmt\b|forensic', 'FMT'), (r'\banaesth|\banesth', 'ANS'), (r'\bphysio', 'PHY'), (r'\bent\b', 'ENT'),
    (r'\bpediatric|\bpaediatric|\bpeds\b', 'PED'), (r'\bophthal', 'OPH'), (r'\bortho', 'ORT'),
    (r'\bsurgery\b', 'SUR'), (r'\bpatho', 'PTH'), (r'\bpsychiatr', 'PSY'), (r'\bradio', 'RAD'),
]
PLACEHOLDER_SUBJECTS = {'Expert Curated', 'Imported'}


def source_subject(source: str) -> str | None:
    name = (source or '').lower().replace('_', ' ')
    if 'pyq' not in name or 'paper' in name or 'question-paper' in name:
        return None  # only per-subject compilations ("<subject> pyqs.pdf")
    for pattern, code in SOURCE_KEYWORDS:
        if re.search(pattern, name):
            return code
    return None


def text_of(q: dict) -> str:
    parts = [q['question_text'], q['option_a'], q['option_b'], q['option_c'], q['option_d']]
    return fold(' '.join(p or '' for p in parts))


def stem_key(q: dict) -> str:
    return ' '.join(re.findall(r'[a-z0-9]+', fold(q['question_text'] or '')))[:200]


def main(argv=None):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, classification_report, f1_score
    from sklearn.model_selection import StratifiedKFold, cross_val_predict
    from sklearn.pipeline import make_pipeline

    from questions.models import Question, Subject

    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--csv', required=True)
    ap.add_argument('--apply-local', action='store_true')
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)
    os.makedirs(os.path.dirname(args.csv), exist_ok=True)

    subjects = {s.code: s for s in Subject.objects.all()}
    name_of = {s.id: s.name for s in subjects.values()}
    rows = list(Question.objects.filter(is_active=True).values(
        'id', 'exam_type', 'year', 'source', 'subject_id', 'question_text',
        'option_a', 'option_b', 'option_c', 'option_d'))

    trusted, seen = [], set()
    for q in rows:
        if q['exam_type'] != 'neet_pg':
            continue
        code = source_subject(q['source'])
        if code and code in subjects:
            q['label'] = code
            key = stem_key(q)
            q['dup'] = key in seen
            seen.add(key)
            trusted.append(q)

    agree = sum(1 for q in trusted if q['subject_id'] == subjects[q['label']].id)
    unique = [q for q in trusted if not q['dup']]
    labels = [q['label'] for q in unique]
    counts = Counter(labels)
    keep_classes = {c for c, n in counts.items() if n >= 10}
    unique = [q for q in unique if q['label'] in keep_classes]
    X = [text_of(q) for q in unique]
    y = [q['label'] for q in unique]

    def model():
        return make_pipeline(
            TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True, max_features=200_000),
            LogisticRegression(max_iter=3000, C=8.0),
        )

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    pred = cross_val_predict(model(), X, y, cv=cv)
    metrics = {
        'trusted_questions': len(trusted),
        'trusted_unique_stems_used': len(unique),
        'classes': sorted(keep_classes),
        'current_tag_agrees_with_source_label': agree,
        'current_tag_agreement_rate': round(agree / len(trusted), 4) if trusted else 0.0,
        'cv_accuracy': round(accuracy_score(y, pred), 4),
        'cv_macro_f1': round(f1_score(y, pred, average='macro'), 4),
        'cv_report': classification_report(y, pred, output_dict=True, zero_division=0),
    }
    print(json.dumps({k: v for k, v in metrics.items() if k != 'cv_report'}, indent=1), flush=True)

    clf = model().fit(X, y)
    classes = list(clf.classes_)
    suggestions = []
    for q in trusted:  # deterministic: source-file label
        target = subjects[q['label']]
        if q['subject_id'] != target.id:
            suggestions.append({'id': q['id'], 'exam_type': q['exam_type'], 'year': q['year'], 'source': q['source'],
                                'current': name_of.get(q['subject_id'], ''), 'suggested': target.name,
                                'confidence': 1.0, 'method': 'source_file',
                                'stem': ' '.join((q['question_text'] or '').split())[:120]})
    trusted_ids = {q['id'] for q in trusted}
    pending = [q for q in rows if q['id'] not in trusted_ids and (
        q['exam_type'] == 'neet_pg' or name_of.get(q['subject_id']) in PLACEHOLDER_SUBJECTS)]
    if pending:
        probs = clf.predict_proba([text_of(q) for q in pending])
        for q, p in zip(pending, probs):
            best = max(range(len(classes)), key=lambda i: p[i])
            target = subjects[classes[best]]
            if target.id == q['subject_id']:
                continue
            suggestions.append({'id': q['id'], 'exam_type': q['exam_type'], 'year': q['year'], 'source': q['source'],
                                'current': name_of.get(q['subject_id'], ''), 'suggested': target.name,
                                'confidence': round(float(p[best]), 3), 'method': 'classifier',
                                'stem': ' '.join((q['question_text'] or '').split())[:120]})

    with open(args.csv, 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=['id', 'exam_type', 'year', 'source', 'current', 'suggested',
                                           'confidence', 'method', 'stem'])
        w.writeheader()
        w.writerows(suggestions)

    by_method = Counter(s['method'] for s in suggestions)
    transitions = Counter((s['current'], s['suggested']) for s in suggestions if s['method'] == 'source_file')
    conf_buckets = Counter(
        '>=0.9' if s['confidence'] >= 0.9 else '0.7-0.9' if s['confidence'] >= 0.7 else '<0.7'
        for s in suggestions if s['method'] == 'classifier')
    summary = {**{k: v for k, v in metrics.items() if k != 'cv_report'},
               'per_class_f1': {c: round(v['f1-score'], 3) for c, v in metrics['cv_report'].items() if c in keep_classes},
               'suggestions_by_method': dict(by_method),
               'classifier_confidence_buckets': dict(conf_buckets),
               'top_source_file_corrections': [[a, b, n] for (a, b), n in transitions.most_common(15)],
               'csv': args.csv}

    applied = 0
    if args.apply_local:
        if not settings.DEBUG:
            raise SystemExit('--apply-local is refused unless DEBUG=True (local database only).')
        by_name = {s.name: s for s in subjects.values()}
        for s in suggestions:
            if s['method'] == 'source_file':
                applied += Question.objects.filter(id=s['id']).update(subject=by_name[s['suggested']])
        summary['applied_locally_source_file_corrections'] = applied
    with open(os.path.join(args.out, 'subject_audit.json'), 'w', encoding='utf-8') as fh:
        json.dump(summary, fh, indent=1)
    print(json.dumps({k: summary[k] for k in ('suggestions_by_method', 'classifier_confidence_buckets')}), flush=True)
    print('applied', applied)
    return summary


if __name__ == '__main__':
    main(sys.argv[1:])
