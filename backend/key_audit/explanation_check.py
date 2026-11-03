"""Explicit answer statements in a question's explanation (answer-key audit, 2026-11).

An explanation that names another answer than the stored key is a strong risk signal: the key or
the explanation is wrong (a copied explanation, options re-ordered by an import, a key typed
wrong). Detected statements, strongest first:

* an answer label: ``"Ans. (b)"``, ``"Answer: (d) Multiple polyps"``, ``"Correct answer: B"``,
  ``"The correct option is D"``, ``"Answer is option D"`` (``questions.answer_leak.find_labels``,
  which skips prompts such as "Select the correct answer" and "ANS" for the autonomic nervous
  system). When the label repeats an option's text, the text decides the option (an explanation
  copied from a source with the options in another order still names the right option);
* ``"Option C is correct"`` / ``"C is the correct answer"`` -- not for EXCEPT / NOT / false
  questions, where explanations call the true distractors "correct";
* statement combinations: ``"Statements 1 and 3 are correct; statement 2 is incorrect"`` or
  ``"Only 1 and 3 are correct"`` mapped to the option ``"1 and 3 only"`` -- only when the
  explanation covers every statement the options use, or says "only";
* pair counts: ``"Only two pairs are correctly matched"`` mapped to the option ``"Only two"``.

An explanation that agrees with the key is not evidence for it (explanations are often written
for the stored key, many by an AI); only disagreement is used, as a signal for human review.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

LETTERS = ('A', 'B', 'C', 'D')
OPTION_FIELDS = ('option_a', 'option_b', 'option_c', 'option_d')

ABSENT = 'absent'
NO_STATEMENT = 'no_statement'
SUPPORTS_KEY = 'supports_key'
STATES_OTHER = 'states_other'
AMBIGUOUS = 'ambiguous'

_TAG_RE = re.compile(r'<[^<>]{0,400}>')
_IMG_TOKEN_RE = re.compile(r'\[\[img:\d+\]\]')
_ROMAN = {'i': 1, 'ii': 2, 'iii': 3, 'iv': 4, 'v': 5, 'vi': 6, 'vii': 7, 'viii': 8, 'ix': 9, 'x': 10}
_WORDS = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6}
_NUM = r'(?:\d{1,2}|viii|vii|vi|iv|ix|iii|ii|v|x|i)'
_ITEM = r'\(?' + _NUM + r'\)?'
_LIST = _ITEM + r'(?:\s*(?:,\s*(?:and\s+)?|&|\band\b)\s*' + _ITEM + r')*'
_TRUE = r'(?:correct|true|right|accurate|valid)'
_FALSE = r'(?:incorrect|false|wrong|untrue|inaccurate|not\s+(?:correct|true))'

_OPTION_IS_CORRECT_RES = (
    re.compile(r'(?<![A-Za-z])option\s*\(?\s*([A-Da-d])\s*\)?\s+is\s+(?:the\s+)?(?:correct|right|best|true)'
               r'(?:\s+(?:answer|option|choice|response))?(?![A-Za-z])', re.IGNORECASE),
    re.compile(r'(?<![A-Za-z])\(?([A-D])\)?\s+is\s+the\s+(?:correct|right|best)\s+(?:answer|option|choice|response)'
               r'(?![A-Za-z])'),
)
_NEGATIVE_STEM_RE = re.compile(
    r"(?<![A-Za-z])(?:except|not|false|incorrect|untrue|wrong|least|never|unlikely|cannot|isn't|aren't|"
    r"doesn't|don't|exception|inappropriate|contraindicated)(?![A-Za-z])", re.IGNORECASE)

_STMT_TRUE_RE = re.compile(
    r'(?<![A-Za-z])(?P<only>only\s+)?(?:statements?|options?|nos?\.?|numbers?)\s+(?P<list>' + _LIST + r')\s+'
    r'(?:is|are)\s+(?:also\s+)?(?:both\s+|all\s+)?' + _TRUE + r'(?![A-Za-z])', re.IGNORECASE)
_ONLY_TRUE_RE = re.compile(
    r'(?<![A-Za-z])only\s+(?P<list>' + _LIST + r')\s+(?:is|are)\s+' + _TRUE + r'(?![A-Za-z])', re.IGNORECASE)
_STMT_FALSE_RE = re.compile(
    r'(?<![A-Za-z])(?:statements?|options?)\s+(?P<list>' + _LIST + r')\s+(?:is|are)\s+(?:also\s+)?' + _FALSE
    + r'(?![A-Za-z])', re.IGNORECASE)
_ALL_TRUE_RE = re.compile(
    r'(?<![A-Za-z])all\s+(?:the\s+)?(?:(?:two|three|four|five|\d)\s+)?(?:of\s+the\s+)?(?:above\s+|given\s+)?'
    r'statements?\s+(?:given\s+)?(?:above\s+)?(?:are\s+)?' + _TRUE + r'(?![A-Za-z])', re.IGNORECASE)
_NONE_TRUE_RE = re.compile(
    r'(?<![A-Za-z])none\s+of\s+the\s+(?:above\s+|given\s+)?statements?\s+(?:is|are)\s+' + _TRUE + r'(?![A-Za-z])',
    re.IGNORECASE)

_COUNT = r'(?:one|two|three|four|five|six|\d)'
_MATCHED = r'(?:correctly|properly|rightly|appropriately|accurately)\s+matched'
_PAIRS_RE = re.compile(
    r'(?<![A-Za-z])(?:only\s+)?(?:the\s+)?(?P<n>' + _COUNT + r')\s+(?:of\s+the\s+(?:above\s+|given\s+)?)?pairs?\s+'
    r'(?:is|are)\s+' + _MATCHED, re.IGNORECASE)
_ALL_PAIRS_RE = re.compile(
    r'(?<![A-Za-z])all\s+(?:the\s+)?(?:(?P<n>' + _COUNT + r')\s+)?(?:of\s+the\s+)?pairs?\s+(?:given\s+)?(?:above\s+)?'
    r'(?:is|are)\s+' + _MATCHED, re.IGNORECASE)
_NO_PAIRS_RE = re.compile(
    r'(?<![A-Za-z])(?:none\s+of\s+the\s+(?:above\s+|given\s+)?pairs?|no\s+pairs?)\s+(?:is|are)\s+' + _MATCHED,
    re.IGNORECASE)


@dataclass(frozen=True)
class Statement:
    letter: str
    method: str      # label | label_text | option_is_correct | statements | pair_count
    field: str
    excerpt: str


def _get(row, name, default=''):
    if isinstance(row, dict):
        return row.get(name, default)
    return getattr(row, name, default)


def plain(text) -> str:
    """Text without markup / image tokens, whitespace collapsed (newlines kept)."""
    if not isinstance(text, str) or not text:
        return ''
    text = _IMG_TOKEN_RE.sub(' ', text)
    text = re.sub(r'(?i)<br\s*/?>|</p>|</div>|</li>', '\n', text)
    text = _TAG_RE.sub(' ', text).replace('&nbsp;', ' ').replace('&amp;', '&')
    return '\n'.join(' '.join(line.split()) for line in text.splitlines()).strip()


def norm(text) -> str:
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', plain(text).lower()).split())


def explanation_texts(row) -> list:
    """[(field, text)] the student sees as the explanation: the locked admin override or the
    curated explanation, plus ``why_correct``."""
    out = []
    override = _get(row, 'admin_explanation_override') or ''
    if _get(row, 'lock_explanation', False) and isinstance(override, str) and override.strip():
        out.append(('admin_explanation_override', override))
    else:
        out.append(('explanation', _get(row, 'explanation') or ''))
    out.append(('why_correct', _get(row, 'why_correct') or ''))
    return [(name, text) for name, text in out if isinstance(text, str) and text.strip()]


def _options(row) -> dict:
    return {letter: _get(row, field) or '' for letter, field in zip(LETTERS, OPTION_FIELDS)}


def _numbers(list_text: str) -> frozenset:
    out = set()
    for token in re.findall(r'\d{1,2}|[ivx]+', list_text.lower()):
        if token.isdigit():
            out.add(int(token))
        elif token in _ROMAN:
            out.add(_ROMAN[token])
    return frozenset(out)


_SET_OPTION_RE = re.compile(
    r'(?:only\s+)?(?:statements?\s+)?(?:both\s+)?(?P<list>' + _LIST + r')(?:\s+only)?(?:\s+(?:is|are)\s+' + _TRUE + r')?',
    re.IGNORECASE)
_ALL_OPTION_RE = re.compile(
    r'all(?:\s+of\s+(?:the\s+)?(?:above|these|them))?(?:\s+(?:the\s+)?(?:above|statements?))?(?:\s+are\s+' + _TRUE + r')?',
    re.IGNORECASE)
_NONE_OPTION_RE = re.compile(r'none(?:\s+of\s+(?:the\s+)?(?:above|these|them|statements?))?', re.IGNORECASE)
_NEITHER_OPTION_RE = re.compile(r'neither\s+' + _LIST + r'\s+nor\s+' + _LIST, re.IGNORECASE)


def option_statement_set(text):
    """The statements an option selects: a frozenset of numbers, 'ALL', or None (not a statement code)."""
    value = plain(text).strip().rstrip('.').strip()
    if not value or len(value) > 60:
        return None
    if _ALL_OPTION_RE.fullmatch(value):
        return 'ALL'
    if _NONE_OPTION_RE.fullmatch(value) or _NEITHER_OPTION_RE.fullmatch(value):
        return frozenset()
    match = _SET_OPTION_RE.fullmatch(value)
    if match:
        numbers = _numbers(match.group('list'))
        return numbers or None
    return None


def _count(token):
    token = (token or '').lower()
    if token.isdigit():
        return int(token)
    return _WORDS.get(token)


_COUNT_OPTION_RE = re.compile(r'(?:only\s+)?(?P<n>' + _COUNT + r')(?:\s+pairs?)?(?:\s+only)?', re.IGNORECASE)
_ALL_COUNT_OPTION_RE = re.compile(r'all\s+(?:the\s+)?(?:(?P<n>' + _COUNT + r')\s+)?(?:pairs?)?', re.IGNORECASE)
_NONE_COUNT_OPTION_RE = re.compile(r'none(?:\s+of\s+(?:the\s+)?(?:above|pairs?|given\s+pairs?))?(?:\s+pairs?)?|no\s+pairs?',
                                   re.IGNORECASE)


def option_pair_count(text):
    """How many pairs an option says are matched: an int, ('ALL', n or None), or None."""
    value = ' '.join(re.sub(r'[^A-Za-z0-9 ]+', ' ', plain(text)).split())
    if not value or len(value) > 40:
        return None
    match = _ALL_COUNT_OPTION_RE.fullmatch(value)
    if match and value.lower().startswith('all'):
        return ('ALL', _count(match.group('n')))
    if _NONE_COUNT_OPTION_RE.fullmatch(value):
        return 0
    match = _COUNT_OPTION_RE.fullmatch(value)
    if match:
        return _count(match.group('n'))
    return None


def _excerpt(text: str, start: int, end: int) -> str:
    return ' '.join(text[max(0, start - 30):min(len(text), end + 50)].split())[:140]


def _text_after_label(text: str, end: int) -> str:
    tail = plain(text[end:end + 240]).split('\n')[0]
    tail = re.split(r'(?i)\b(?:explanation|reason|ref(?:erence)?|because|as\s+per)\b|[;]|\.\s', tail)[0]
    return tail.strip(' .:-–—)')


def _option_by_text(tail: str, options: dict) -> str:
    """The one option whose text the label repeats ('' when none or several)."""
    tail_n = norm(tail)
    if len(tail_n) < 2:
        return ''
    hits = []
    for letter, text in options.items():
        option_n = norm(text)
        if not option_n:
            continue
        if tail_n == option_n or tail_n.startswith(option_n + ' ') or (len(tail_n) >= 4 and option_n.startswith(tail_n + ' ')):
            hits.append(letter)
    return hits[0] if len(hits) == 1 else ''


def _label_statements(field: str, text: str, options: dict) -> list:
    from questions.answer_leak import ANSWER, find_labels

    out = []
    for label in find_labels(text):
        if label.kind != ANSWER or label.letter not in LETTERS:
            continue
        by_text = _option_by_text(_text_after_label(text, label.end), options)
        if by_text and by_text != label.letter:
            out.append(Statement(by_text, 'label_text', field, _excerpt(text, label.start, label.end)))
        else:
            out.append(Statement(label.letter, 'label', field, _excerpt(text, label.start, label.end)))
    return out


def _option_is_correct_statements(field: str, text: str) -> list:
    out = []
    flat = plain(text)
    for regex in _OPTION_IS_CORRECT_RES:
        for match in regex.finditer(flat):
            out.append(Statement(match.group(1).upper(), 'option_is_correct', field,
                                 _excerpt(flat, match.start(), match.end())))
    return out


def _statement_combination(field: str, text: str, options: dict, stem: str):
    sets = {letter: option_statement_set(value) for letter, value in options.items()}
    parsed = {letter: value for letter, value in sets.items() if value is not None}
    if len(parsed) < 3:
        return None
    universe = frozenset().union(*[value for value in parsed.values() if value != 'ALL'])
    if not universe:
        return None
    flat = plain(text)
    true_sets, false_sets, only, first = [], [], False, None
    for match in _STMT_TRUE_RE.finditer(flat):
        true_sets.append(_numbers(match.group('list')))
        only = only or bool(match.group('only'))
        first = first or match
    for match in _ONLY_TRUE_RE.finditer(flat):
        true_sets.append(_numbers(match.group('list')))
        only = True
        first = first or match
    for match in _STMT_FALSE_RE.finditer(flat):
        false_sets.append(_numbers(match.group('list')))
        first = first or match
    all_true = _ALL_TRUE_RE.search(flat)
    none_true = _NONE_TRUE_RE.search(flat)
    positive = frozenset().union(*true_sets) if true_sets else frozenset()
    negative = frozenset().union(*false_sets) if false_sets else frozenset()
    if all_true and not negative:
        target, first = universe, first or all_true
    elif none_true and not positive:
        target, first = frozenset(), first or none_true
    elif not true_sets and not false_sets:
        return None
    elif positive & negative:
        return None
    elif only:
        target = positive
    elif (positive | negative) >= universe:
        target = positive & universe
    else:
        return None
    hits = [letter for letter, value in parsed.items() if (universe if value == 'ALL' else value) == target]
    if len(hits) != 1:
        return None
    return Statement(hits[0], 'statements', field, _excerpt(flat, first.start(), first.end()))


def _pair_count(field: str, text: str, options: dict, stem: str):
    if 'pair' not in (stem or '').lower():
        return None
    counts = {letter: option_pair_count(value) for letter, value in options.items()}
    parsed = {letter: value for letter, value in counts.items() if value is not None}
    if len(parsed) < 3:
        return None
    flat = plain(text)
    stated = None
    match = _NO_PAIRS_RE.search(flat)
    if match:
        stated = 0
    else:
        match = _ALL_PAIRS_RE.search(flat)
        if match:
            stated = ('ALL', _count(match.group('n')))
        else:
            match = _PAIRS_RE.search(flat)
            if match:
                stated = _count(match.group('n'))
    if stated is None or match is None:
        return None
    hits = []
    for letter, value in parsed.items():
        if isinstance(stated, tuple):
            if isinstance(value, tuple) or (stated[1] is not None and value == stated[1]):
                hits.append(letter)
        elif value == stated or (isinstance(value, tuple) and value[1] == stated):
            hits.append(letter)
    if len(hits) != 1:
        return None
    return Statement(hits[0], 'pair_count', field, _excerpt(flat, match.start(), match.end()))


def statements(row) -> list:
    """Every answer statement the explanation fields make, strongest kind first."""
    options = _options(row)
    stem = _get(row, 'question_text') or ''
    negative = bool(_NEGATIVE_STEM_RE.search(plain(stem)))
    labels, option_claims, derived = [], [], []
    for field, text in explanation_texts(row):
        labels += _label_statements(field, text, options)
        if not negative:
            option_claims += _option_is_correct_statements(field, text)
        for finder in (_statement_combination, _pair_count):
            found = finder(field, text, options, stem)
            if found:
                derived.append(found)
    return labels or option_claims or derived


def check_explanation(row) -> dict:
    """``{status, stated_key, method, field, excerpt, letters}`` for a Question or a dict.

    status: 'absent' (no explanation text), 'no_statement', 'supports_key', 'states_other'
    (one stated answer, not the stored key -- also when the key is invalid), 'ambiguous'
    (the statements name several options).
    """
    texts = explanation_texts(row)
    key = (_get(row, 'correct_answer') or '').strip().upper()[:1]
    result = {'status': ABSENT, 'stated_key': '', 'method': '', 'field': '', 'excerpt': '', 'letters': []}
    if not texts:
        return result
    found = statements(row)
    letters = sorted({s.letter for s in found})
    result['letters'] = letters
    if not found:
        result['status'] = NO_STATEMENT
        return result
    if len(letters) > 1:
        result.update(status=AMBIGUOUS, method=found[0].method, field=found[0].field, excerpt=found[0].excerpt)
        return result
    first = found[0]
    result.update(stated_key=first.letter, method=first.method, field=first.field, excerpt=first.excerpt,
                  status=SUPPORTS_KEY if first.letter == key else STATES_OTHER)
    return result
