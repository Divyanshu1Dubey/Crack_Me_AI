"""Answer keys and explanations that leaked into a question's public text.

Some imports glued the answer key or the explanation into the stem or an
option: option D ``"I and IV only Correct Answer: A. I, II and IV only"``,
a stem ending in ``"\\n\\nExplanation: ..."``, an option D followed by the
answer-key table and the worked solutions of a whole paper, or whole pasted
pages of questions with their ``"Ans: (b) ..."`` lines. Others printed a
correctness flag on an option -- ``"Conjunctival xerosis ✔ (Conjunctival
xerosis is the first clinical sign ...)"``, ``"Adrenaline (correct)"``,
``"[wrong]"``, a tick or a cross -- or on the options a stem lists inline
(``"A. Schwannoma ✅"``). The stem and the options are public (every list
row, test payload and search result shows them), so that text gave the
answer away to callers who may not read it
(``questions.views.user_can_view_answer``).

* ``find_labels`` / ``find_flags`` / ``row_has_answer_label`` -- the
  detector (plain ``re``, no Django import, so importers can use it too).
* ``redact_public_text`` -- the serving guard, built on
  ``cut_option_text`` (an option up to its first label or flag, with a flag
  that leads it dropped, and the reason after a flag gone with it) and
  ``redact_stem_text`` (a stem up to its first label -- ``cut_at_answer_label``
  -- without the flags and their reasons on the options it lists).
* ``plan_repair`` -- the data repair of ``manage.py fix_answer_label_leaks``
  and of ``import_mocktests`` before it saves a question.
* ``label_hold_reasons`` -- hold codes for the import / publish gates.

Labels and headings wrapped in HTML (the rich-text DOCX import:
``"<p><strong>Explanation</strong></p>"``, ``"<strong>Ans:</strong> (b)"``)
count as well.

Not labels: prompts such as "Select the correct answer:" / "Choose the
correct answer -", assertion-reason wording such as "R is the correct
explanation of A", and "ANS" for the autonomic nervous system ("(ANS)",
"of the ANS: (a) ..."). A bracketed "(Ans)" / "[ans.]" in mixed or lower
case on an option is a flag. Not flags: "(right)" (a side: "Hepatic flexure
(right)"), the upper-case "(ANS)", "(correctly placed)", "Statement II is correct", an
option that is just the word "Correct", a last line "correct" / "wrong" that
ends a wrapped sentence ("Only 1 is\\ncorrect", "Both 1 and 2 are\\ncorrect"),
and a tick in a stem outside the options it lists.

``questions.locked_text_search`` keeps the text filters (question-bank
``?search=``, recall search) from matching inside the cut-away part.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

PUBLIC_TEXT_FIELDS = ('question_text', 'option_a', 'option_b', 'option_c', 'option_d')
OPTION_FIELDS = ('option_a', 'option_b', 'option_c', 'option_d')
OPTION_LETTERS = ('A', 'B', 'C', 'D')

# One question's key: "Correct Answer: B.", "Ans: (b)", "Answer - C", "Ans. is 'a' i.e. ...".
ANSWER = 'answer'
# The key / solutions of a whole set: "Answer Key", "Detailed Explanations",
# "Solution to Question 3:".
ANSWER_KEY = 'answer_key'
# "Explanation: ...", an "Explanation" heading line, "Trap Explanation:", "Why: ...".
EXPLANATION = 'explanation'
# A correctness flag: a tick / cross, "(correct)", "[Correct answer]",
# "(wrong)", "(right answer)", "(answer)".
FLAG = 'flag'
CORRECT = 'correct'
WRONG = 'wrong'

_Q = r"['‘’\"“”]?"
# Inline rich-text tags that may sit between the parts of a label
# ("<strong>Ans:</strong> (b)", "<b>Correct Answer</b>: B").
_INLINE_TAG = r"</?(?:strong|b|em|i|u|span|font|mark|sup|sub)\b[^<>\n]{0,80}>"
_INLINE_TAG_RE = re.compile(_INLINE_TAG)
_G = r"(?:\s|" + _INLINE_TAG + r")*"
# The option letter after a label: "(b)", an upper-case letter on its own
# ("B", "B.", "'B'") or a lower-case one closed by punctuation ("b)", "b.").
# A bare lower-case letter is a word ("the correct answer is a ...").
_LETTER = (
    r"(?:\(\s*(?P<p>[A-Da-d])\s*\)"
    r"|" + _Q + r"(?P<u>[A-D])" + _Q + r"(?![A-Za-z0-9])"
    r"|" + _Q + r"(?P<l>[a-d])" + _Q + r"(?=[.):\]]|</))"
)
# After "Ans. is" (the Indian MCQ-book convention) a bare letter is the key.
_LETTER_AFTER_ANS_IS = (
    r"(?:\(\s*(?P<p>[A-Da-d])\s*\)|" + _Q + r"(?P<u>[A-Da-d])" + _Q + r"(?![A-Za-z0-9]))"
)
_ANSWER_LABEL_RES = (
    re.compile(
        r"(?<![A-Za-z])(?i:correct\s+(?:answer|ans|option|choice|response)s?)" + _G +
        r"(?:(?i:is)" + _G + r"[:\-–—]?|[:\-–—=])" + _G + r"(?:(?i:option)\s*)?" + _LETTER
    ),
    re.compile(
        r"(?<![A-Za-z])(?i:answers?|ans)" + _G + r"(?:[:\-–—=)<]|\.)" + _G +
        r"(?:(?i:is)\s+)?(?:(?i:option)\s*)?" + _LETTER
    ),
    re.compile(
        r"(?<![A-Za-z])(?i:answer)\s+(?i:is)" + _G + r"[:\-–—]?" + _G + r"(?:(?i:option)\s*)?" + _LETTER
    ),
    # "Answer ( a ) ..." with no punctuation in between.
    re.compile(r"(?<![A-Za-z])(?i:answers?|ans)\.?" + _G + r"\(\s*(?P<p>[A-Da-d])\s*\)"),
    re.compile(r"(?<![A-Za-z])(?i:ans)\.?\s*(?i:is)\s+(?:(?i:option)\s*)?" + _LETTER_AFTER_ANS_IS),
)
# Where a heading may start / what may wrap it: a new line, or the next
# block of rich text ("...</p><p><strong>Explanation</strong></p>").
_BLOCK_START = r"(?:^|(?<=\n)|(?<=</p>)|(?<=</div>)|(?<=<br>)|(?<=<br/>)|(?<=<br />))"
_OPEN_TAGS = r"(?:<[A-Za-z][^<>\n]{0,200}>[ \t]*)*"
_CLOSE_TAGS = r"(?:[ \t]*</[A-Za-z][^<>\n]{0,40}>)*"
_ANSWER_KEY_RES = (
    re.compile(r"(?<![A-Za-z])(?i:answer\s+keys?)(?![A-Za-z])"),
    re.compile(r"(?<![A-Za-z])(?i:solutions?\s+(?:to|of|for)\s+(?:question|q)s?\.?\s*(?:no\.?\s*)?\d+)"),
    re.compile(
        _BLOCK_START + r"[ \t]*" + _OPEN_TAGS + r"(?i:detailed\s+(?:explanations?|solutions?|answers?))"
        + _CLOSE_TAGS + r"[ \t]*(?=\n|$|<)"
    ),
)
_EXPLANATION_LABEL_RES = (
    re.compile(
        r"(?<![A-Za-z])(?:(?i:trap)\s+)?(?i:explanations?)(?:\s*" + _INLINE_TAG + r")*\s*(?::|[-–—]\s)"
    ),
    # A heading line (or block) followed by the explanation itself: the next
    # line / block holds text or an opening tag, not only closing tags.
    re.compile(
        _BLOCK_START + r"[ \t]*" + _OPEN_TAGS + r"(?i:explanations?)" + _CLOSE_TAGS
        + r"[ \t]*(?=(?:\n|<(?!/))\s*(?:[^\s<]|<(?!/)))"
    ),
    re.compile(_BLOCK_START + r"[ \t]*" + _OPEN_TAGS + r"(?i:why)(?:\s*" + _INLINE_TAG + r")*\s*:(?=\s*\S)"),
)
# "Select the correct answer:" / "Choose the correct answer -": a prompt that
# introduces the options, not an answer key.
_PROMPT_BEFORE_RE = re.compile(
    r"(?i:(?<![A-Za-z])(?:select|choose|mark|pick|tick|identify|indicate|find|give|circle|"
    r"encircle|write|underline)\s+(?:out\s+)?(?:the\s+|your\s+|an?\s+)?(?:most\s+)?"
    r"(?:correct\s+|right\s+|best\s+|appropriate\s+|true\s+)?)$"
)
# "ANS" is also the autonomic nervous system: "(ANS)", or a capitalised
# "ANS" after an article / preposition ("of the ANS: (a) ...").
_ANS_ABBREVIATION_BEFORE_RE = re.compile(
    r"(?<![A-Za-z])(?i:the|of|on|in|and|or|to|by|via|from|with|both|its|their|central|peripheral|enteric)\s+$"
)
_IMG_TOKEN_RE = re.compile(r"\[\[img:\d+\]\]")
_TAG_RE = re.compile(r"<[^<>]{0,400}>")
_IMG_TAG_RE = re.compile(r"<img\b", re.IGNORECASE)
# A list number left alone on the last line once a label is cut off
# ("4. ...\n5. Explanation: ..." keeps "4. ..." and drops the stray "5.").
_TRAILING_ENUM_RE = re.compile(r"(?:^|\n)[ \t]*\(?(?:\d{1,2}|[ivxlIVXL]{1,4}|[a-eA-E])[.)][ \t]*$")
# Opening tags (not images) left at the end once a label is cut off.
_TRAILING_OPEN_TAGS_RE = re.compile(r"(?:\s*<(?!/|img\b)[A-Za-z][^<>]{0,200}>)+\s*$", re.IGNORECASE)
_TRAILING_CLOSE_TAGS_RE = re.compile(r"(?:\s*</[A-Za-z][A-Za-z0-9]*\s*>)+\s*$")
_LEADING_IE_RE = re.compile(r"^(?i:i\.?\s?e\.?)[,:]?\s*")
_LEADING_WHY_RE = re.compile(r"^(?i:why|reason|because|explanation)s?\s*[:\-–—]\s*")

# Correctness flags. Ticks: ✓ ✔ ✅ ☑; crosses: ✗ ✘ ❌ ❎ ☒ ✖ (U+FE0F, the
# emoji variation selector, may follow).
_GLYPHS_CORRECT = "✓✔✅☑"
_GLYPHS_WRONG = "✗✘❌❎☒✖"
_GLYPH = "[" + _GLYPHS_CORRECT + _GLYPHS_WRONG + "]️?"
_GLYPH_RUN = _GLYPH + r"(?:[ \t]*" + _GLYPH + r")*"
# "(correct)", "[Correct answer]", "(incorrect)", "(wrong)", "(right answer)",
# "(answer)" -- not "(right)" (a side).
_FLAG_WORD = (
    r"(?P<word>(?:in)?correct|wrong|answer"
    r"|right(?=[ \t]+(?:answer|ans|option|choice)(?![A-Za-z])))"
    r"(?:[ \t]+(?:answer|ans|option|choice|one))?"
)
# "(Ans)" / "[ans.]" in mixed or lower case marks the answer on an option.
# The exact upper-case "(ANS)" is the autonomic nervous system and stays text.
_ANS_FLAG = r"(?P<aword>(?!ANS(?![A-Za-z]))(?i:ans))"
_FLAG_RE = re.compile(
    r"[(\[][ \t]*(?:(?i:" + _FLAG_WORD + r")[ \t]*\.?|" + _ANS_FLAG + r"[ \t]*\.?"
    r"|(?P<bglyph>" + _GLYPH_RUN + r"))[ \t]*[)\]]"
    r"|(?P<glyph>" + _GLYPH_RUN + r")"
)
# The flag column of a rich-text import pasted as the option's last line /
# paragraph: "<p>Adrenaline</p>\n<p>correct</p>", "Adrenaline\nCorrect".
_TRAILING_FLAG_LINE_RE = re.compile(
    r"(?:(?<=\n)|(?<=<br>)|(?<=<br/>)|(?<=<br />)|(?<=</p>)|(?<=</div>))[ \t]*" + _OPEN_TAGS
    + r"(?i:(?P<word>(?:in)?correct|wrong)(?:[ \t]+(?:answer|option))?)[ \t]*\.?" + _CLOSE_TAGS + r"\s*\Z"
)
# ... unless the text before that line ends in a copula, an article or a
# quantifier: then "correct" / "wrong" ends a wrapped sentence ("Only 1 is\n
# correct", "Both 1 and 2 are\ncorrect", "Reason is\nwrong"). "a" only in
# lower case ("Vitamin A\nCorrect" is a flag).
_SENTENCE_GOES_ON_RE = re.compile(
    r"(?<![A-Za-z])(?:(?i:is|are|was|were|be|been|not|the|an|both|all|none|neither|either|only|also)|a)"
    r"[ \t]*\Z"
)
# SQL pre-filter of the scans (``manage.py fix_answer_label_leaks``,
# ``questions.locked_text_search``): a row can only carry a label or a
# correctness flag if one of these words / ticks / crosses occurs in its
# public text (``icontains``).
PREFILTER_WORDS = (
    'ans', 'correct', 'explanation', 'why', 'solution', 'detailed', 'wrong', 'right',
    *_GLYPHS_CORRECT, *_GLYPHS_WRONG,
)
# Cheap pre-check: every flag holds one of these.
_MAYBE_FLAG_RE = re.compile(
    "[" + _GLYPHS_CORRECT + _GLYPHS_WRONG + "]"
    r"|[(\[][ \t]*(?i:(?:in)?correct|wrong|right|answer|ans)"
    r"|(?i:correct|wrong)[ \t]*\.?(?:[ \t]*</[A-Za-z][^<>\n]{0,40}>)*\s*\Z"
)
# An option / statement enumerator followed by its text: "A.", "(b)", "c)",
# "1.", "(ii)" at the start of a line or inline ("... A. Schwannoma B. ...").
_ENUM_RE = re.compile(r"(?:^|(?<=[\s>]))\(?(?P<enum>[A-Ea-e]|\d{1,2}|[ivxIVX]{1,4})[.)](?=[ \t]+\S)")


@dataclass(frozen=True)
class Label:
    kind: str          # ANSWER, ANSWER_KEY, EXPLANATION or FLAG
    start: int
    end: int
    letter: str = ''   # 'A'-'D' for an ANSWER label (and a stem FLAG on a lettered option)
    polarity: str = ''  # FLAG: CORRECT or WRONG
    trailing: bool = False  # FLAG: the option's last line ("Adrenaline\ncorrect"), a weaker signal


def _letter_of(match) -> str:
    for value in match.groupdict().values():
        if value:
            return value.upper()
    return ''


# Cheap pre-check: every label starts with one of these words.
_MAYBE_LABEL_RE = re.compile(r"(?i)(?<![a-z])(?:ans|correct|explanation|why|solution|detailed)")


def _ans_is_abbreviation(text: str, start: int) -> bool:
    """True when the "ans" at ``start`` names the autonomic nervous system:
    "(ANS)" in any case, or a capitalised "ANS" after an article /
    preposition ("involvement of the ANS. A 30-year-old ...")."""
    if text[start:start + 3].lower() != 'ans' or text[start + 3:start + 4].isalpha():
        return False
    if start and text[start - 1] == '(' and text[start + 3:].lstrip(' \t.').startswith(')'):
        return True
    return text[start:start + 3] == 'ANS' and bool(
        _ANS_ABBREVIATION_BEFORE_RE.search(text[max(0, start - 16):start])
    )


def find_labels(text) -> list:
    """Every answer / answer-key / explanation label in ``text``, by position."""
    if not isinstance(text, str) or not text or not _MAYBE_LABEL_RE.search(text):
        return []
    found = {}
    for regex in _ANSWER_LABEL_RES:
        for match in regex.finditer(text):
            # (Inline tags dropped: "Choose the <strong>correct answer</strong>: (a) ...")
            window = _INLINE_TAG_RE.sub('', text[max(0, match.start() - 96):match.start()])[-48:]
            if _PROMPT_BEFORE_RE.search(window) or _ans_is_abbreviation(text, match.start()):
                continue
            found.setdefault(match.start(), Label(ANSWER, match.start(), match.end(), _letter_of(match)))
    for kind, regexes in ((ANSWER_KEY, _ANSWER_KEY_RES), (EXPLANATION, _EXPLANATION_LABEL_RES)):
        for regex in regexes:
            for match in regex.finditer(text):
                found.setdefault(match.start(), Label(kind, match.start(), match.end()))
    # "Correct Answer: B" also holds the "Answer: B" match: keep the outer
    # (earliest) label and drop any that starts inside it.
    out = []
    for label in sorted(found.values(), key=lambda item: (item.start, -item.end)):
        if out and label.start < out[-1].end:
            continue
        out.append(label)
    return out


def has_answer_label(text) -> bool:
    return bool(find_labels(text))


# ── Correctness flags ────────────────────────────────────────────────────


def _visible(text) -> str:
    """``text`` without image tokens, markup (an ``<img>`` counts as content)
    and surrounding space: empty when nothing would show."""
    if not isinstance(text, str) or not text:
        return ''
    text = _IMG_TOKEN_RE.sub('', text)
    if _IMG_TAG_RE.search(text):
        return text.strip()
    return _TAG_RE.sub('', text).replace('&nbsp;', ' ').strip()


def _polarity(match) -> str:
    word = match.groupdict().get('word')
    if word:
        return WRONG if word.lower() in ('incorrect', 'wrong') else CORRECT
    groups = match.groupdict()
    if groups.get('aword'):
        return CORRECT
    glyphs = groups.get('bglyph') or groups.get('glyph') or ''
    return CORRECT if glyphs[:1] in _GLYPHS_CORRECT else WRONG


@dataclass(frozen=True)
class _StemFlag:
    start: int         # first character removed (the space before the flag)
    stop: int          # first character kept after the removal
    token_start: int   # the flag itself
    token_end: int
    letter: str        # 'A'-'D' when the flag sits on a lettered option
    polarity: str
    reason: str        # text after the flag that goes with it
    joiner: str        # what replaces the removed span ('' or ' ')
    lead: bool         # the flag leads the option text ("A. ✅ Schwannoma")


def _matching_close(text: str, index: int, end: int):
    """Index of the bracket closing the one at ``index`` (before ``end``)."""
    opener = text[index]
    closer = ')' if opener == '(' else ']'
    depth = 0
    for position in range(index, end):
        char = text[position]
        if char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return position
    return None


def _stem_flag_spans(text: str) -> list:
    """Flags on the options / statements a stem lists ("A. Schwannoma ✅",
    "(b) Adrenaline (correct)", "1. ... ✔"), each with the span to remove:
    the flag and the reason after it, up to the next listed option or the
    end of the line. A flag that leads the option text loses only itself.
    A flag outside a listed option is left alone (a tick in a table)."""
    spans = []
    for match in _FLAG_RE.finditer(text):
        if spans and match.start() < spans[-1].stop:
            continue  # inside the reason of the previous flag
        line_start = text.rfind('\n', 0, match.start()) + 1
        line_end = text.find('\n', match.end())
        if line_end < 0:
            line_end = len(text)
        enums = [e for e in _ENUM_RE.finditer(text, line_start, line_end) if e.end() <= match.start()]
        if not enums:
            continue
        last, first = enums[-1].group('enum'), enums[0].group('enum')
        letter = ''
        if (len(last) == 1 and last.upper() in OPTION_LETTERS
                and len(first) == 1 and first.upper() in 'ABCDE'):
            letter = last.upper()
        polarity = _polarity(match)
        if not _visible(text[enums[-1].end():match.start()]):
            stop = match.end()
            while stop < line_end and text[stop] in ' \t':
                stop += 1
            spans.append(_StemFlag(match.start(), stop, match.start(), match.end(), letter, polarity, '', '', True))
            continue
        start = match.start()
        while start > line_start and text[start - 1] in ' \t':
            start -= 1
        cursor = match.end()
        while cursor < line_end and text[cursor] in ' \t':
            cursor += 1
        if cursor < line_end and text[cursor] in '([':
            close = _matching_close(text, cursor, line_end)
            cursor = line_end if close is None else close + 1
        following = _ENUM_RE.search(text, cursor, line_end)
        if following:
            stop, joiner = following.start(), ' '
        else:
            # Keep the closing tags that end the line ("...✅</p>").
            tail = _TRAILING_CLOSE_TAGS_RE.search(text, cursor, line_end)
            stop, joiner = (tail.start() if tail else line_end), ''
        spans.append(_StemFlag(start, stop, match.start(), match.end(), letter, polarity,
                               _reason_text(text[match.end():stop]), joiner, False))
    return spans


def find_flags(text, *, stem: bool = False) -> list:
    """Every correctness flag in ``text`` (``FLAG`` labels with their
    ``polarity``), by position. On an option (the default) any flag counts;
    with ``stem=True`` only the flags on the options / statements the stem
    lists, with the letter of a lettered option."""
    if not isinstance(text, str) or not text or not _MAYBE_FLAG_RE.search(text):
        return []
    if stem:
        return [Label(FLAG, span.token_start, span.token_end, span.letter, span.polarity)
                for span in _stem_flag_spans(text)]
    flags = [Label(FLAG, m.start(), m.end(), polarity=_polarity(m)) for m in _FLAG_RE.finditer(text)]
    tail = _TRAILING_FLAG_LINE_RE.search(text)
    if tail and not any(f.start <= tail.start() < f.end for f in flags):
        before = _visible(text[:tail.start()])
        if before and not _SENTENCE_GOES_ON_RE.search(before):
            flags.append(Label(FLAG, tail.start(), tail.end(), polarity=_polarity(tail), trailing=True))
    return sorted(flags, key=lambda item: item.start)


def has_option_leak(text) -> bool:
    """True when an option's text carries an answer / explanation label or
    a correctness flag."""
    return bool(find_labels(text) or find_flags(text))


def _option_dict_values(options):
    if isinstance(options, dict):
        return list(options.values())
    if isinstance(options, (list, tuple)):
        return [item.get('text') for item in options if isinstance(item, dict)]
    return []


def row_has_answer_label(row) -> bool:
    """True when the public text of ``row`` (a dict or a Question) carries a
    label, or a correctness flag on an option or on an option its stem
    lists. A dict row may carry its options as ``options`` (``{'A': ..}``)."""
    if isinstance(row, dict):
        get = row.get
    else:
        def get(name, default=None):
            return getattr(row, name, default)
    stem = get('question_text')
    if has_answer_label(stem) or find_flags(stem, stem=True):
        return True
    if any(has_option_leak(get(name)) for name in OPTION_FIELDS):
        return True
    return isinstance(row, dict) and any(has_option_leak(value) for value in _option_dict_values(row.get('options')))


# ── Serving guard ────────────────────────────────────────────────────────


def _close_dangling_brackets(head: str) -> str:
    """Close (or drop, when nothing follows it) a bracket the cut left open
    on the last line: "Adrenaline (Correct Answer: B)" -> "Adrenaline",
    "Adrenaline (1 mg ✓)" -> "Adrenaline (1 mg)"."""
    line_start = head.rfind('\n') + 1
    while True:
        stack = []
        for index in range(line_start, len(head)):
            char = head[index]
            if char in '([':
                stack.append(index)
            elif char in ')]' and stack:
                stack.pop()
        if not stack:
            return head
        index = stack[-1]
        inner = head[index + 1:].rstrip(' \t,;:-–—/')
        if not _visible(inner):
            head = head[:index].rstrip()
        else:
            head = head[:index + 1] + inner + (')' if head[index] == '(' else ']')


def _reclose_tags(head: str, removed: str) -> str:
    """Re-append the closing tags at the end of the removed part that the
    kept part still needs ("<p>Adrenaline ✔ (...)</p>" -> "<p>Adrenaline</p>")."""
    tail = _TRAILING_CLOSE_TAGS_RE.search(removed or '')
    if not tail or '<' not in head:
        return head
    for name in re.findall(r"</([A-Za-z][A-Za-z0-9]*)", tail.group(0)):
        opened = len(re.findall(r"<" + name + r"(?=[\s>])", head, re.IGNORECASE))
        closed = len(re.findall(r"</" + name + r"\s*>", head, re.IGNORECASE))
        if opened > closed:
            head += f'</{name}>'
    return head


def _tidy_head(head: str, removed: str = '') -> str:
    """The kept part of a cut text: without the opening tags, the stray list
    number ("5.") and the open bracket the cut left at its end, plus the
    closing tags it still needs."""
    for _ in range(3):  # one step can expose the next ("4. ...\n5. (" -> "4. ...")
        before = head
        head = _TRAILING_OPEN_TAGS_RE.sub('', head.rstrip()).rstrip()
        head = _TRAILING_ENUM_RE.sub('', head).rstrip()
        head = _close_dangling_brackets(head)
        if head == before:
            break
    return _reclose_tags(head, removed)


def _head_before(text: str, start: int) -> str:
    return _tidy_head(text[:start], text[start:])


def _keep_image_tokens(head: str, removed: str) -> str:
    """Re-append the ``[[img:N]]`` tokens of a removed tail (a stem figure
    still renders; explanation figures are filtered by role elsewhere)."""
    tokens = [tok for tok in dict.fromkeys(_IMG_TOKEN_RE.findall(removed)) if tok not in head]
    if tokens:
        head = (head + '\n\n' + '\n'.join(tokens)).strip()
    return head


def cut_at_answer_label(text):
    """``text`` up to its first label (non-strings and label-free text come
    back unchanged)."""
    labels = find_labels(text)
    if not labels:
        return text
    start = labels[0].start
    return _keep_image_tokens(_head_before(text, start), text[start:])


def _option_events(text: str):
    """``(lead, rest)``: the flags that lead an option (nothing visible
    before them) and the labels / flags after its text, by position."""
    events = sorted(find_labels(text) + find_flags(text), key=lambda item: (item.start, -item.end))
    merged = []
    for event in events:
        if merged and event.start < merged[-1].end:
            continue
        merged.append(event)
    lead, position = [], 0
    for index, event in enumerate(merged):
        if event.kind == FLAG and not _visible(text[position:event.start]):
            lead.append(event)
            position = event.end
            continue
        return lead, merged[index:]
    return lead, []


def _without_lead_flags(text: str, lead) -> str:
    """``text`` minus the leading flags (and the space after each)."""
    out, position = [], 0
    for flag in lead:
        out.append(text[position:flag.start])
        position = flag.end
        while position < len(text) and text[position] in ' \t':
            position += 1
    out.append(text[position:])
    return ''.join(out)


def _split_option(text: str):
    """``(new_text, lead, rest, cut)`` of one option: its text without the
    leading flags, cut at its first label / flag."""
    lead, rest = _option_events(text)
    cut = rest[0].start if rest else len(text)
    kept = _without_lead_flags(text[:cut], lead)
    if rest:
        new_text = _keep_image_tokens(_tidy_head(kept, text[cut:]), text[cut:])
    else:
        new_text = kept.strip()
    return new_text, lead, rest, cut


def cut_option_text(text):
    """An option as a viewer without the answer sees it: up to its first
    label or correctness flag (the reason after a flag goes with it), and a
    flag that leads the option dropped ("Conjunctival xerosis ✔ (...)" ->
    "Conjunctival xerosis", "(correct) Adrenaline" -> "Adrenaline").
    Non-strings and clean text come back unchanged."""
    if not isinstance(text, str) or not text:
        return text
    new_text, lead, rest, _ = _split_option(text)
    return new_text if (lead or rest) else text


def _strip_stem_flags(text: str):
    """``(text, spans)``: ``text`` without the flags (and their reasons) on
    the options / statements it lists."""
    spans = _stem_flag_spans(text) if isinstance(text, str) and _MAYBE_FLAG_RE.search(text or '') else []
    out = text
    for span in reversed(spans):
        head = out[:span.start]
        if not span.lead:
            head = _close_dangling_brackets(head)
        out = head + span.joiner + out[span.stop:]
    return out, spans


def redact_stem_text(text):
    """A stem as a viewer without the answer sees it: up to its first label
    (``cut_at_answer_label``), without the flags on the options it lists."""
    if not isinstance(text, str) or not text:
        return text
    return _strip_stem_flags(cut_at_answer_label(text))[0]


def redact_public_text(data: dict) -> bool:
    """Cut the public text of a serialized row for a viewer who may not read
    its answer: the stem with ``redact_stem_text``, each option (also an
    ``options`` dict ``{'A': ..}`` / list of ``{'text': ..}``) with
    ``cut_option_text``. Returns True when something was removed."""
    changed = False
    value = data.get('question_text')
    if isinstance(value, str) and value:
        cut = redact_stem_text(value)
        if cut != value:
            data['question_text'] = cut
            changed = True
    for name in OPTION_FIELDS:
        value = data.get(name)
        if isinstance(value, str) and value:
            cut = cut_option_text(value)
            if cut != value:
                data[name] = cut
                changed = True
    options = data.get('options')
    if isinstance(options, dict):
        cut = {key: cut_option_text(value) if isinstance(value, str) else value for key, value in options.items()}
        if cut != options:
            data['options'] = cut
            changed = True
    elif isinstance(options, list):
        cut = [
            {**item, 'text': cut_option_text(item['text'])}
            if isinstance(item, dict) and isinstance(item.get('text'), str) else item
            for item in options
        ]
        if cut != options:
            data['options'] = cut
            changed = True
    return changed


def label_hold_reasons(question_text, options) -> list:
    """Hold codes for an import / publish gate: the stem or an option
    carries an answer label, an explanation label or a correctness flag.
    ``options`` is an iterable of option texts."""
    options = list(options or [])
    kinds = set()
    for text in [question_text, *options]:
        kinds.update(label.kind for label in find_labels(text))
    reasons = []
    if kinds & {ANSWER, ANSWER_KEY}:
        reasons.append('answer_label_in_public_text')
    if EXPLANATION in kinds:
        reasons.append('explanation_label_in_public_text')
    if any(find_flags(text) for text in options):
        reasons.append('answer_flag_in_option')
    if find_flags(question_text, stem=True):
        reasons.append('answer_flag_in_stem')
    return reasons


# ── Data repair ──────────────────────────────────────────────────────────


def _norm(text) -> str:
    return re.sub(r'[^a-z0-9]+', '', (text or '').lower())


def _strip_tokens(text: str) -> str:
    return _IMG_TOKEN_RE.sub('', text or '').strip()


def _reason_text(text: str) -> str:
    """The reason printed after a correctness flag, as explanation text:
    "(Conjunctival xerosis is the first ...)" -> "Conjunctival xerosis is
    the first ..."."""
    text = _TRAILING_CLOSE_TAGS_RE.sub('', _strip_tokens(text)).strip()
    text = text.lstrip(' \t\n-–—:;,.').strip()
    if len(text) >= 2 and text[0] in '([' and _matching_close(text, 0, len(text)) == len(text) - 1:
        text = text[1:-1].strip()
    text = _LEADING_WHY_RE.sub('', text).strip()
    return text if re.search(r'[A-Za-z0-9]', _visible(text)) else ''


def _rest_after_option_text(body: str, option_text: str):
    """``body`` minus a leading copy of ``option_text`` (compared without
    case / punctuation), or None when ``body`` does not start with it."""
    target = _norm(option_text)
    if not target:
        return None
    seen = ''
    for index, char in enumerate(body):
        if char.isalnum():
            seen += char.lower()
        if len(seen) >= len(target):
            return body[index + 1:].lstrip(' \t\n.,;:-–—)').rstrip() if seen == target else None
    return None


@dataclass
class Repair:
    """What ``plan_repair`` would change on one question."""
    changes: dict = field(default_factory=dict)   # field -> new value
    actions: list = field(default_factory=list)   # human-readable steps
    deactivate: bool = False                      # hold the row for manual review
    reasons: list = field(default_factory=list)   # why it is held
    conflict: bool = False                        # labelled / flagged key unusable / disagrees
    category: str = ''                            # main kind of leak
    conflicts: list = field(default_factory=list)  # what disagrees, for the review report

    @property
    def needed(self) -> bool:
        return bool(self.changes or self.deactivate)

    def add_conflict(self, text: str) -> None:
        self.conflict = True
        self.actions.append(text)
        self.conflicts.append(text)


def plan_repair(row) -> Repair:
    """Plan the repair of one question (a dict or a Question with
    ``question_text``, ``option_a``..``option_d``, ``correct_answer``,
    ``explanation`` and optionally ``lock_answer`` / ``lock_explanation``).

    * An answer label inside an option ("<option> Correct Answer: B. <text
      of B>") is cut off. Its letter becomes the key when the stored key is
      empty and the label repeats option B's text; a stored key that differs
      is kept (``conflict``).
    * A correctness flag on an option ("<option> ✔ (<reason>)", "(correct)",
      "[wrong]") is dropped and its reason moves to ``explanation``. A single
      option flagged correct names the key: it fills an empty key; a stored
      key that differs -- or a stored key whose option is flagged wrong -- is
      kept and reported (``conflict``). Flags on the options a stem lists
      ("A. Schwannoma ✅") are dropped the same way (and only reported).
    * An answer-key table / worked solutions of a whole set after an option
      are cut off and dropped (they are other questions' answers).
    * An explanation label in the stem or an option: the text after it moves
      to ``explanation``, which keeps a real explanation it already holds.
    * A row that cannot be repaired is held for manual review
      (``deactivate``) with its text untouched: a stem holding answer labels
      (a pasted page of questions with their answers), or a stem / an option
      that is nothing but a label or a flag (the real text is missing).
    """
    if isinstance(row, dict):
        get = row.get
    else:
        def get(name, default=None):
            return getattr(row, name, default)
    stem = get('question_text') or ''
    options = {name: get(name) or '' for name in OPTION_FIELDS}
    stored_key = (get('correct_answer') or '').strip().upper()[:1]
    explanation = get('explanation') or ''
    lock_answer = bool(get('lock_answer', False))
    lock_explanation = bool(get('lock_explanation', False))
    repair = Repair()

    def hold(category, reason):
        return Repair(deactivate=True, reasons=[reason], category=category)

    stem_labels = find_labels(stem)
    if any(label.kind in (ANSWER, ANSWER_KEY) for label in stem_labels) or len(stem_labels) > 1:
        return hold('pasted_page', 'the stem holds answer labels (a pasted page of questions and answers)')

    moved = []
    new_options = dict(options)
    label_letters = []   # (letter, text after the label)
    flagged_correct, flagged_wrong = [], []   # option letters
    trailing_correct = []   # letters of options whose last line is "correct"
    for name in OPTION_FIELDS:
        text = options[name]
        new_text, lead, rest, cut = _split_option(text)
        if not lead and not rest:
            continue
        if not _visible(new_text):
            return hold('option_is_label', f'{name} holds only a label / explanation / flag, not option text')
        letter = name[-1].upper()
        new_options[name] = new_text
        repair.changes[name] = new_text
        for flag in lead:
            (flagged_correct if flag.polarity == CORRECT else flagged_wrong).append(letter)
        if lead:
            repair.category = repair.category or 'option_answer_flag'
            repair.actions.append(f'{name}: dropped the correctness flag "{text[lead[0].start:lead[-1].end].strip()}"')
        if rest:
            repair.actions.append(f'{name}: cut "{text[cut:cut + 40].strip()}..."')
        for index, label in enumerate(rest):
            nxt = rest[index + 1].start if index + 1 < len(rest) else len(text)
            if label.kind == FLAG:
                repair.category = repair.category or 'option_answer_flag'
                if label.polarity != CORRECT:
                    flagged_wrong.append(letter)
                elif label.trailing:
                    trailing_correct.append(letter)
                else:
                    flagged_correct.append(letter)
                reason = _reason_text(text[label.end:nxt])
                if reason:
                    moved.append(reason)
                continue
            if label.kind == ANSWER_KEY:
                # The rest is a whole set's key / solutions: dropped.
                repair.category = repair.category or 'option_answer_key'
                repair.actions.append(f'{name}: dropped an answer-key table / set solutions')
                break
            body = _strip_tokens(text[label.end:nxt]).lstrip(' \t\n.:-–—)').rstrip()
            if label.kind == ANSWER:
                repair.category = repair.category or 'option_answer_label'
                if label.letter:
                    label_letters.append((label.letter, _LEADING_IE_RE.sub('', body)))
                else:
                    repair.conflict = True
            elif body:
                repair.category = repair.category or 'option_explanation'
                moved.append(body)

    new_stem = stem
    if len(stem_labels) == 1:
        label = stem_labels[0]
        head = _head_before(stem, label.start)
        if not _visible(head):
            return hold('stem_is_label', 'the stem holds only an explanation, not the question')
        new_stem = _keep_image_tokens(head, stem[label.start:])
        repair.changes['question_text'] = new_stem
        repair.actions.append('question_text: moved the explanation out of the stem')
        repair.category = repair.category or 'stem_explanation'
        body = _strip_tokens(stem[label.end:])
        if body:
            moved.append(body)
    stem_flag_letters = []
    flagged_stem, spans = _strip_stem_flags(new_stem)
    if spans:
        repair.changes['question_text'] = flagged_stem
        repair.actions.append('question_text: dropped the correctness flags on the options it lists')
        repair.category = repair.category or 'stem_answer_flag'
        for span in spans:
            if span.letter and span.polarity == CORRECT:
                stem_flag_letters.append(span.letter)
            if span.reason:
                moved.append(span.reason)

    # The key the label(s) name, checked against the option it names.
    letters = {letter for letter, _ in label_letters}
    if len(letters) > 1:
        repair.add_conflict(f'labels name different keys {sorted(letters)} (none applied)')
    elif letters:
        label_key = next(iter(letters))
        consistent = True
        for letter, body in label_letters:
            if not body:
                continue
            rest = _rest_after_option_text(body, new_options.get(f'option_{letter.lower()}', ''))
            if rest is None:
                consistent = False
            elif rest:
                moved.append(_LEADING_WHY_RE.sub('', rest))
        if stored_key == label_key:
            pass
        elif stored_key in OPTION_LETTERS:
            repair.add_conflict(f'labelled key {label_key} disagrees with the stored key {stored_key} (kept)')
        elif lock_answer:
            repair.actions.append(f'labelled key {label_key} not applied (the answer is locked)')
        elif consistent:
            repair.changes['correct_answer'] = label_key
            repair.actions.append(f'correct_answer: set to {label_key} from the label')
        else:
            repair.add_conflict(f'labelled key {label_key} does not repeat its option text (not applied)')

    # The key the correctness flags name. A flag that is only the option's
    # last line ("Adrenaline\ncorrect") may be a wrapped sentence the
    # detector misread: it never fills an empty key (reported instead).
    flagged = sorted(set(flagged_correct) | set(trailing_correct))
    if len(flagged) > 1:
        repair.add_conflict(f'options {", ".join(flagged)} are all flagged as correct (no key applied)')
    elif flagged:
        flag_key = flagged[0]
        label_key = repair.changes.get('correct_answer')
        if letters and flag_key not in letters:
            repair.changes.pop('correct_answer', None)
            repair.add_conflict(
                f'option {flag_key} is flagged as correct but the label names {", ".join(sorted(letters))} '
                f'(no key applied)'
            )
        elif stored_key == flag_key or label_key == flag_key:
            pass
        elif stored_key in OPTION_LETTERS:
            repair.add_conflict(f'option {flag_key} is flagged as correct but the stored key is {stored_key} (kept)')
        elif lock_answer:
            repair.actions.append(f'flagged key {flag_key} not applied (the answer is locked)')
        elif flag_key not in flagged_correct:
            repair.add_conflict(
                f'option {flag_key} ends in a "correct" line (a flag column?) and the key is empty '
                f'(not applied, review)'
            )
        else:
            repair.changes['correct_answer'] = flag_key
            repair.actions.append(f'correct_answer: set to {flag_key} from the flag on option {flag_key}')
    if stored_key in OPTION_LETTERS and stored_key in flagged_wrong:
        repair.add_conflict(f'option {stored_key} (the stored key) is flagged as wrong (kept)')
    stem_named = sorted(set(stem_flag_letters))
    if stored_key in OPTION_LETTERS and stem_named and stored_key not in stem_named:
        repair.add_conflict(
            f'the stem flags option {", ".join(stem_named)} as correct but the stored key is {stored_key} (kept)'
        )

    moved = [text for text in dict.fromkeys(moved) if text]
    if moved:
        text = '\n\n'.join(moved)
        current = explanation.strip()
        option_norms = {_norm(value) for value in new_options.values() if value}
        if lock_explanation:
            repair.actions.append('explanation: locked by an admin; the moved text only leaves the public fields')
        elif not current or _norm(current) in option_norms:
            # Empty, or just a copy of the answer option (an import artefact).
            repair.changes['explanation'] = text
            repair.actions.append('explanation: set from the moved text')
        elif _norm(text) in _norm(current):
            repair.actions.append('explanation: already holds the moved text')
        else:
            repair.changes['explanation'] = f'{current}\n\n{text}'
            repair.actions.append('explanation: moved text appended')
    return repair
