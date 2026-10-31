"""Retrieval benchmark for the textbook RAG store.

Run (from backend/, against a database holding the question bank):

    DJANGO_ENV_FILE=.env.localdev python -m ai_eval.rag_benchmark --out ../docs/audit/rag

Nothing here calls an LLM or writes to the store (opened read-only).

DATASETS — labels come from data the platform already has; no relevance
judgement is invented:

* ANS (primary). Dated UPSC CMS PYQs (2018–2025). Query = the cleaned stem
  (no options). A chunk is relevant when it is study material (not a raw
  question paper, not an excluded document), contains the full text of the
  correct option, and contains at least one distinctive stem term (document
  frequency <= 2%). Queries whose stem already contains the option text are
  dropped (leakage), as are generic options ("all of the above", numbers).
  Split by year: dev 2018–2021 (tuning), test 2022–2025 (reported).
* KNOWN (coverage smoke test). Dated CMS stems whose first 60 normalised
  characters occur in a question-paper chunk; relevant = those chunks. This
  only checks that the retriever can reach the whole store.
* TOPIC (silver). Stems that mention the topic of one of the topic notes
  (e.g. "malaria" → med_malaria.md); relevant = every chunk of that note.

Metrics are computed on rankings de-duplicated by chunk content: success@k
(hit rate, a.k.a. Recall@k for a single answer-bearing passage), precision@5,
MRR@10, nDCG@10 (binary gains), plus latency, duplicate rate and
question-paper rate of the raw top 5. 95% bootstrap confidence intervals
(paired with the production baseline) are reported for the test split.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import sqlite3
import statistics
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass

if __name__ == '__main__':  # standalone: python -m ai_eval.rag_benchmark
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')
    import django
    django.setup()

from django.conf import settings  # noqa: E402

from ai_engine import lexical_index as lx  # noqa: E402

K = 10
STORE = os.path.join(settings.BASE_DIR, 'chroma_db', 'rag_store.sqlite3')

# ─── helpers ───────────────────────────────────────────────────────────

_NON_ALNUM = re.compile(r'[^a-z0-9]+')


def norm(text: str) -> str:
    return ' '.join(_NON_ALNUM.split(lx.fold(text or ''))).strip()


_NUMBERING = re.compile(r'^\s*(?:q(?:uestion)?\s*\.?\s*)?\d+(?:\s+\d+)?\s*[\.\):\-]\s*', re.IGNORECASE)
_OPTION_LINE = re.compile(r'^\s*(?:\(?[a-dA-D]\)|[a-dA-D][\.\)])\s+')
_ANSWER_LINE = re.compile(r'^\s*(?:answer|ans|explanation)\s*[:\-]', re.IGNORECASE)


def clean_stem(text: str) -> str:
    lines = []
    for line in (text or '').splitlines():
        if _OPTION_LINE.match(line) or _ANSWER_LINE.match(line):
            break
        lines.append(line)
    stem = ' '.join(' '.join(lines).split())
    stem = _NUMBERING.sub('', stem).strip(' :;-')
    return stem


GENERIC_OPTIONS = {
    'all of the above', 'none of the above', 'all the above', 'none of these', 'all of these',
    'both', 'both of the above', 'neither', 'either', 'all', 'none', 'a and b', 'b and c',
    'a and c', 'a b and c', 'both a and b', 'both a and c', 'true', 'false', 'yes', 'no',
}


def usable_option(text: str) -> bool:
    t = norm(text)
    if len(t) < 6 or t in GENERIC_OPTIONS:
        return False
    alpha_tokens = [w for w in t.split() if re.search('[a-z]', w)]
    return len(alpha_tokens) >= 1 and sum(len(w) for w in alpha_tokens) >= 5


def contains_phrase(haystack_norm: str, needle_norm: str) -> bool:
    return f' {needle_norm} ' in f' {haystack_norm} '


# ─── store ─────────────────────────────────────────────────────────────

@dataclass
class Row:
    rowid: int
    chunk_id: str
    text: str
    book: str
    page: int
    source_file: str
    tokens_json: str
    key: str
    norm_text: str
    excluded: bool
    question_paper: bool


def load_store(path: str) -> list[Row]:
    conn = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    try:
        rows = conn.execute(
            'SELECT rowid, id, document, book, page, source_file, tokens FROM chunks ORDER BY rowid').fetchall()
    finally:
        conn.close()
    out = []
    for rowid, cid, text, book, page, source_file, tokens in rows:
        out.append(Row(rowid, cid, text or '', book or '', int(page or 0), source_file or '', tokens or '[]',
                       lx.content_key(text or ''), norm(text or ''),
                       lx.is_excluded_document(book or '', source_file or ''),
                       lx.is_question_paper(book or '', source_file or '')))
    return out


# ─── retrievers ────────────────────────────────────────────────────────

_OLD_STOP = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do',
             'does', 'did', 'will', 'would', 'shall', 'should', 'may', 'might', 'must', 'can', 'could', 'of', 'in',
             'to', 'for', 'with', 'on', 'at', 'from', 'by', 'as', 'or', 'and', 'but', 'not', 'no', 'if', 'so', 'it',
             'its', 'this', 'that', 'these', 'those', 'i', 'me', 'my', 'we', 'our', 'you', 'your', 'he', 'she',
             'they', 'them'}


def old_tokenize(text: str) -> list[str]:
    """Verbatim copy of the pre-2026-11 RAGPipeline._tokenize."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s\-]', ' ', text)
    return [t for t in text.split() if len(t) > 1 and t not in _OLD_STOP]


class OldTfidf:
    """Exact replica of the pre-2026-11 RAGPipeline.search scoring.

    Same tokenizer, the stored token lists, the store's idf_cache values and
    the same cosine; ``cap`` reproduces RAG_MAX_SEARCH_CHUNKS (rowid order).
    IDF is held in a dict here (identical values); ``sql_idf=True`` replays
    the original one-query-per-term lookup for the latency sample.
    """

    def __init__(self, rows: list[Row], store: str, cap: int | None, sql_idf: bool = False):
        self.rows = rows
        self.cap = cap
        conn = sqlite3.connect(f'file:{store}?mode=ro', uri=True)
        self.idf = dict(conn.execute('SELECT term, idf FROM idf_cache').fetchall())
        self.sql_idf = sql_idf
        self.conn = conn if sql_idf else None
        if not sql_idf:
            conn.close()
        self.doc_tokens = [json.loads(r.tokens_json) for r in rows]
        self.doc_tf = [Counter(t) for t in self.doc_tokens]
        self.doc_total = [len(t) or 1 for t in self.doc_tokens]
        # Document norms depend only on the store, so precompute them (same math).
        self.doc_norm = [
            math.sqrt(sum(((tf[t] / total) * self.idf.get(t, 1.0)) ** 2 for t in tf))
            for tf, total in zip(self.doc_tf, self.doc_total)
        ]

    def _idf(self, term):
        if self.sql_idf:
            row = self.conn.execute('SELECT idf FROM idf_cache WHERE term=?', (term,)).fetchone()
            return row[0] if row else 1.0
        return self.idf.get(term, 1.0)

    def search(self, query: str, n: int):
        q = old_tokenize(query)
        if not q:
            return []
        q_tf = Counter(q)
        q_total = len(q)
        limit = len(self.rows) if self.cap is None else min(self.cap, len(self.rows))
        results = []
        if self.sql_idf:
            # Original control flow: IDF looked up per term and per document term.
            for i in range(limit):
                d_tf, d_total = self.doc_tf[i], self.doc_total[i]
                score = 0.0
                for term in set(q):
                    idf = self._idf(term)
                    score += (q_tf[term] / q_total) * idf * (d_tf.get(term, 0) / d_total) * idf
                q_norm = math.sqrt(sum(((q_tf[t] / q_total) * self._idf(t)) ** 2 for t in q_tf))
                d_norm = math.sqrt(sum(((d_tf[t] / d_total) * self._idf(t)) ** 2 for t in d_tf))
                if q_norm and d_norm and score > 0:
                    results.append((score / (q_norm * d_norm), i))
        else:
            q_idf = {t: self._idf(t) for t in q_tf}
            q_norm = math.sqrt(sum(((q_tf[t] / q_total) * q_idf[t]) ** 2 for t in q_tf))
            for i in range(limit):
                d_tf, d_total, d_norm = self.doc_tf[i], self.doc_total[i], self.doc_norm[i]
                score = 0.0
                for term, idf in q_idf.items():
                    c = d_tf.get(term)
                    if c:
                        score += (q_tf[term] / q_total) * idf * (c / d_total) * idf
                if q_norm and d_norm and score > 0:
                    results.append((score / (q_norm * d_norm), i))
        results.sort(key=lambda x: -x[0])
        return [self.rows[i] for _s, i in results[:n]]


class Bm25:
    def __init__(self, rows: list[Row], *, policy: bool, stem: bool = True, include_papers: bool = False,
                 k1: float = 1.2, b: float = 0.75):
        if policy:
            docs, _stats = lx.load_documents(STORE)
        else:
            docs = [lx.Doc(chunk_id=r.chunk_id, text=r.text, book=r.book, page=r.page,
                           source_file=r.source_file, key=r.key, question_paper=r.question_paper) for r in rows]
        self.by_id = {r.chunk_id: r for r in rows}
        self.index = lx.BM25Index(docs, k1=k1, b=b, stem=stem)
        self.include_papers = include_papers or not policy

    def search(self, query: str, n: int):
        hits = self.index.search(query, n, include_question_papers=self.include_papers)
        return [self.by_id[d.chunk_id] for _s, d in hits]


class Fts5:
    """SQLite FTS5 bm25() over the policy corpus (porter + unicode61)."""

    def __init__(self, rows: list[Row], include_papers: bool = False):
        docs, _ = lx.load_documents(STORE)
        if not include_papers:
            docs = [d for d in docs if not d.question_paper]
        self.by_id = {r.chunk_id: r for r in rows}
        self.ids = [d.chunk_id for d in docs]
        self.conn = sqlite3.connect(':memory:')
        self.conn.execute("CREATE VIRTUAL TABLE f USING fts5(body, tokenize='porter unicode61 remove_diacritics 2')")
        self.conn.executemany('INSERT INTO f(rowid, body) VALUES (?, ?)',
                              ((i, lx.fold(d.text)) for i, d in enumerate(docs)))

    def search(self, query: str, n: int):
        terms = [t for t in lx.tokenize(query, stem=False)]
        if not terms:
            return []
        match = ' OR '.join(f'"{t}"' for t in dict.fromkeys(terms))
        rows = self.conn.execute('SELECT rowid FROM f WHERE f MATCH ? ORDER BY bm25(f) LIMIT ?', (match, n)).fetchall()
        return [self.by_id[self.ids[r[0]]] for r in rows]


# ─── datasets ──────────────────────────────────────────────────────────

TOPIC_TERMS = {
    'med_malaria.md': ['malaria'], 'med_ckd.md': ['chronic kidney disease', 'ckd'], 'med_dengue.md': ['dengue'],
    'med_diabetes.md': ['diabetes mellitus', 'diabetic'], 'med_hypertension.md': ['hypertension'],
    'med_pneumonia.md': ['pneumonia'], 'med_rheumatic_fever.md': ['rheumatic fever'],
    'med_sle.md': ['systemic lupus', 'sle'], 'med_thyroid.md': ['thyroid'], 'med_tuberculosis.md': ['tuberculosis'],
    'med_typhoid.md': ['typhoid', 'enteric fever'], 'micro_hep_b.md': ['hepatitis b', 'hbsag', 'hbv'],
    'micro_hiv.md': ['hiv'], 'obg_ectopic.md': ['ectopic'], 'obg_gdm.md': ['gestational diabetes'],
    'obg_pcos.md': ['pcos', 'polycystic ovar'], 'obg_placenta_previa.md': ['placenta previa', 'placenta praevia'],
    'obg_preeclampsia.md': ['preeclampsia', 'pre eclampsia'], 'path_leukemia.md': ['leukemia', 'leukaemia'],
    'peds_chd.md': ['congenital heart'], 'peds_immunization.md': ['immunization', 'immunisation'],
    'peds_kawasaki.md': ['kawasaki'], 'peds_malnutrition.md': ['malnutrition', 'kwashiorkor', 'marasmus'],
    'peds_measles.md': ['measles'], 'peds_neonatal_jaundice.md': ['neonatal jaundice'],
    'peds_nephrotic_syndrome.md': ['nephrotic syndrome'], 'pharm_amr.md': ['antimicrobial resistance'],
    'pharm_nsaids.md': ['nsaid'], 'psm_biostatistics.md': ['standard deviation', 'chi square'],
    'psm_demography.md': ['sex ratio', 'fertility rate'], 'psm_nhm.md': ['national health mission'],
    'psm_occupational_health.md': ['pneumoconiosis', 'silicosis', 'occupational'],
    'psm_water_purification.md': ['chlorination', 'residual chlorine'], 'surg_appendicitis.md': ['appendicitis'],
    'surg_breast_cancer.md': ['breast cancer', 'carcinoma breast', 'breast carcinoma'],
    'surg_gallstones.md': ['gallstone', 'cholelithiasis', 'cholecystitis'], 'surg_hernia.md': ['hernia'],
    'surg_intestinal_obstruction.md': ['intestinal obstruction'], 'fmed_autopsy.md': ['autopsy', 'postmortem'],
    'fmed_rigor_mortis.md': ['rigor mortis'], 'med_anemia.md': ['anemia', 'anaemia'],
}


def load_questions():
    from questions.models import Question
    qs = (Question.objects.filter(exam_type='cms', is_active=True, year__gte=2018, year__lte=2025)
          .exclude(correct_answer__isnull=True).exclude(correct_answer='')
          .values('id', 'year', 'question_text', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_answer'))
    seen, out = set(), []
    for q in qs.iterator():
        stem = clean_stem(q['question_text'])
        key = norm(stem)
        if len(key) < 20 or key in seen:  # one copy per stem (duplicates exist across years)
            continue
        seen.add(key)
        q['stem'] = stem
        out.append(q)
    return out


def build_datasets(rows: list[Row], questions: list[dict]):
    knowledge = [r for r in rows if not r.excluded and not r.question_paper]
    papers = [r for r in rows if r.question_paper]
    padded = {id(r): f' {r.norm_text} ' for r in knowledge}
    df = Counter()
    for r in knowledge:
        df.update(set(r.norm_text.split()))
    n_know = len(knowledge)
    rare_cut = 0.02 * n_know

    ans, known, topic = [], [], []
    stats = Counter()
    for q in questions:
        stem_norm = norm(q['stem'])
        split = 'dev' if q['year'] <= 2021 else 'test'
        # KNOWN
        prefix = stem_norm[:60]
        if len(prefix) >= 40:
            rel = {r.key for r in papers if prefix in r.norm_text}
            if rel:
                known.append({'qid': q['id'], 'year': q['year'], 'split': split, 'query': q['stem'], 'relevant': sorted(rel)})
        # TOPIC
        rel_files = {f for f, terms in TOPIC_TERMS.items() if any(contains_phrase(stem_norm, norm(t)) for t in terms)}
        if rel_files:
            rel = {r.key for r in knowledge if r.source_file in rel_files}
            if rel:
                topic.append({'qid': q['id'], 'year': q['year'], 'split': split, 'query': q['stem'],
                              'topics': sorted(rel_files), 'relevant': sorted(rel)})
        # ANS
        letter = (q['correct_answer'] or '').strip().upper()[:1]
        option = q.get(f'option_{letter.lower()}') or ''
        stats['ans_candidates'] += 1
        if not usable_option(option):
            stats['ans_generic_option'] += 1
            continue
        opt_norm = norm(option)
        if contains_phrase(stem_norm, opt_norm):
            stats['ans_option_in_stem'] += 1
            continue
        rare_terms = {w for w in set(stem_norm.split()) if len(w) > 3 and 0 < df.get(w, 0) <= rare_cut}
        if not rare_terms:
            stats['ans_no_rare_terms'] += 1
            continue
        needle = f' {opt_norm} '
        rare_needles = [f' {t} ' for t in rare_terms]
        rel = {r.key for r in knowledge
               if needle in padded[id(r)] and any(t in padded[id(r)] for t in rare_needles)}
        if not rel:
            stats['ans_not_covered'] += 1
            continue
        ans.append({'qid': q['id'], 'year': q['year'], 'split': split, 'query': q['stem'],
                    'answer_text': option.strip(), 'relevant': sorted(rel)})
    stats.update({'ans': len(ans), 'known': len(known), 'topic': len(topic), 'knowledge_chunks': n_know,
                  'question_paper_chunks': len(papers)})
    return {'ANS': ans, 'KNOWN': known, 'TOPIC': topic}, dict(stats)


# ─── metrics ───────────────────────────────────────────────────────────

def score_query(retrieved: list[Row], relevant: set[str]) -> dict:
    ranking, seen = [], set()
    for r in retrieved:
        if r.key not in seen:
            seen.add(r.key)
            ranking.append(r)
    hits = [1 if r.key in relevant else 0 for r in ranking[:K]]
    first = next((i for i, h in enumerate(hits) if h), None)
    dcg = sum(h / math.log2(i + 2) for i, h in enumerate(hits))
    idcg = sum(1 / math.log2(i + 2) for i in range(min(len(relevant), K)))
    raw5 = retrieved[:5]
    dup5 = sum(1 for i, r in enumerate(raw5) if r.key in {x.key for x in raw5[:i]})
    return {
        's1': int(any(hits[:1])), 's3': int(any(hits[:3])), 's5': int(any(hits[:5])), 's10': int(any(hits[:10])),
        'p5': sum(hits[:5]) / 5, 'mrr': (1 / (first + 1)) if first is not None else 0.0,
        'ndcg': (dcg / idcg) if idcg else 0.0,
        'dup5': dup5 / max(1, len(raw5)), 'qp5': sum(1 for r in raw5 if r.question_paper) / max(1, len(raw5)),
        'excl5': sum(1 for r in raw5 if r.excluded) / max(1, len(raw5)),
    }


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def bootstrap(per_q_a: list[float], per_q_b: list[float] | None = None, iters: int = 1000, seed: int = 7):
    """95% CI of mean(a) (or of mean(a-b) when b is given, paired)."""
    rnd = random.Random(seed)
    n = len(per_q_a)
    if n == 0:
        return (0.0, 0.0)
    vals = [a - b for a, b in zip(per_q_a, per_q_b)] if per_q_b is not None else per_q_a
    means = []
    for _ in range(iters):
        sample = [vals[rnd.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    return (round(means[int(0.025 * iters)], 4), round(means[int(0.975 * iters) - 1], 4))


def evaluate(name, retriever, dataset, rows_by_key=None):
    per_q, lat = [], []
    for item in dataset:
        t = time.perf_counter()
        got = retriever.search(item['query'], K)
        lat.append((time.perf_counter() - t) * 1000)
        res = score_query(got, set(item['relevant']))
        res['qid'] = item['qid']
        res['split'] = item['split']
        per_q.append(res)
    return per_q, lat


def summarise(per_q, lat):
    keys = ['s1', 's3', 's5', 's10', 'p5', 'mrr', 'ndcg', 'dup5', 'qp5', 'excl5']
    out = {k: round(mean([r[k] for r in per_q]), 4) for k in keys}
    out['n'] = len(per_q)
    if lat:
        s = sorted(lat)
        out['latency_ms_p50'] = round(statistics.median(s), 2)
        out['latency_ms_p95'] = round(s[min(len(s) - 1, int(0.95 * len(s)))], 2)
    return out


# ─── offline answer check ──────────────────────────────────────────────

def offline_answer_check(retriever, dataset, limit=None):
    """Extractive answers from the top-5 passages: does the answer contain the
    correct option text, and is every sentence verbatim from its source?"""
    contains, faithful, answered, total = 0, 0, 0, 0
    for item in dataset[:limit] if limit else dataset:
        total += 1
        got = retriever.search(item['query'], 5)
        passages = [{'text': r.text, 'book': r.book, 'page': r.page} for r in got]
        ans = lx.extractive_answer(item['query'], passages)
        if not ans:
            continue
        answered += 1
        if contains_phrase(norm(ans['answer']), norm(item['answer_text'])):
            contains += 1
        sentences = [re.sub(r'\s*\[[^\]]+\]$', '', line[2:]) for line in ans['answer'].splitlines() if line.startswith('- ')]
        if all(any(s in p['text'] for p in passages) for s in sentences):
            faithful += 1
    return {'queries': total, 'answered': answered, 'answer_contains_correct_option': contains,
            'verbatim_faithful_answers': faithful,
            'answer_contains_rate': round(contains / total, 4) if total else 0.0}


# ─── main ──────────────────────────────────────────────────────────────

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(settings.BASE_DIR, '..', 'docs', 'audit', 'rag'))
    ap.add_argument('--latency-sample', type=int, default=25)
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)

    t0 = time.perf_counter()
    rows = load_store(STORE)
    questions = load_questions()
    datasets, ds_stats = build_datasets(rows, questions)
    print('datasets', ds_stats, f'{time.perf_counter() - t0:.1f}s', flush=True)

    builders = {
        'prod_tfidf_cap2000': lambda: OldTfidf(rows, STORE, cap=2000),
        'tfidf_nocap': lambda: OldTfidf(rows, STORE, cap=None),
        'bm25_raw_store': lambda: Bm25(rows, policy=False),
        'bm25_policy (shipped)': lambda: Bm25(rows, policy=True),
        'bm25_policy_nostem': lambda: Bm25(rows, policy=True, stem=False),
        'bm25_policy_k1.5_b0.6': lambda: Bm25(rows, policy=True, k1=1.5, b=0.6),
        'fts5_porter_policy': lambda: Fts5(rows),
    }
    known_builders = {
        'prod_tfidf_cap2000': lambda: OldTfidf(rows, STORE, cap=2000),
        'tfidf_nocap': lambda: OldTfidf(rows, STORE, cap=None),
        'bm25_policy+papers': lambda: Bm25(rows, policy=True, include_papers=True),
        'fts5_porter_policy+papers': lambda: Fts5(rows, include_papers=True),
    }

    results = {'datasets': ds_stats, 'retrievers': {}, 'known': {}, 'build_seconds': {}}
    per_query = {}
    for name, make in builders.items():
        t = time.perf_counter()
        retr = make()
        results['build_seconds'][name] = round(time.perf_counter() - t, 2)
        entry = {}
        for ds in ('ANS', 'TOPIC'):
            per_q, lat = evaluate(name, retr, datasets[ds])
            per_query[(name, ds)] = per_q
            entry[ds] = {split: summarise([r for r, l in zip(per_q, lat) if r['split'] == split],
                                          [l for r, l in zip(per_q, lat) if r['split'] == split])
                         for split in ('dev', 'test')}
        entry['offline_answers_ANS_test'] = offline_answer_check(retr, [d for d in datasets['ANS'] if d['split'] == 'test'])
        results['retrievers'][name] = entry
        print(name, json.dumps({ds: entry[ds]['test'] for ds in ('ANS', 'TOPIC')}), flush=True)

    for name, make in known_builders.items():
        retr = make()
        per_q, lat = evaluate(name, retr, datasets['KNOWN'])
        results['known'][name] = summarise(per_q, lat)
        print('KNOWN', name, results['known'][name], flush=True)

    # Paired bootstrap on the ANS test split vs the production baseline.
    base = [r for r in per_query[('prod_tfidf_cap2000', 'ANS')] if r['split'] == 'test']
    results['bootstrap_ANS_test'] = {}
    for name in builders:
        cur = [r for r in per_query[(name, 'ANS')] if r['split'] == 'test']
        results['bootstrap_ANS_test'][name] = {
            m: {'mean': round(mean([r[m] for r in cur]), 4), 'ci95': bootstrap([r[m] for r in cur]),
                'diff_vs_prod_ci95': bootstrap([r[m] for r in cur], [r[m] for r in base])}
            for m in ('s5', 'mrr', 'ndcg')
        }

    # Real production latency: original one-SQL-query-per-term IDF lookups.
    sample = [d for d in datasets['ANS'] if d['split'] == 'test'][: args.latency_sample]
    slow = OldTfidf(rows, STORE, cap=2000, sql_idf=True)
    _pq, lat = evaluate('prod_sql_idf', slow, sample)
    results['production_latency_sample'] = summarise(_pq, lat)
    print('prod latency sample', results['production_latency_sample'], flush=True)

    # Shipped index build time / size.
    t = time.perf_counter()
    lx.invalidate()
    _idx, st = lx.get_index(STORE)
    results['shipped_index'] = {'build_seconds': round(time.perf_counter() - t, 2), 'docs': st.docs_indexed,
                                'rows_in_store': st.rows_in_store, 'alias_copies_dropped': st.dropped_alias_copies,
                                'duplicates_dropped': st.dropped_duplicate_content,
                                'excluded_document_chunks': st.dropped_excluded_documents,
                                'question_paper_docs': st.question_paper_docs, 'terms': st.terms}

    with open(os.path.join(args.out, 'benchmark_results.json'), 'w', encoding='utf-8') as fh:
        json.dump(results, fh, indent=1)
    with open(os.path.join(args.out, 'eval_set_ANS.jsonl'), 'w', encoding='utf-8') as fh:
        for d in datasets['ANS']:
            fh.write(json.dumps({k: d[k] for k in ('qid', 'year', 'split', 'query', 'answer_text')}) + '\n')
    print('done', f'{time.perf_counter() - t0:.1f}s', flush=True)
    return results


if __name__ == '__main__':
    main(sys.argv[1:])
