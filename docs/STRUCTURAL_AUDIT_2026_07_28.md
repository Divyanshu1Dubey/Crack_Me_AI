# Structural Audit — CrackCMS Question Bank

**Date**: 2026-07-28
**Auditor**: Claude Opus 4.8
**Database**: Production Postgres (cracklabs.app), snapshot taken at audit run
**Tool**: `backend/scripts/structural_audit_2026_07_28.py`
**Raw output**: `docs/STRUCTURAL_AUDIT_2026_07_28.json`

---

## Summary

| Metric | Value |
|---|---|
| Total questions audited | **13,788** |
| Unique structural shapes | 12 |
| Already structured (no work needed) | 1,617 (11.7%) |
| Inlined / malformed (work needed) | ~469 (3.4%) |
| Normal prose / short question (no work needed) | 11,147 (80.8%) |
| Remaining unresolved after 0027+0029+0030 | 499 (3.6%) |

After migration **0027** (HTML/leak cleanup), **0029** (fidelity `<p>correct</p>` cleanup), and **0030** (inlined-statement split), the question bank is in significantly better shape. This audit confirms where the remaining work is.

---

## Per-Shape Inventory

### ✅ Already structured (1,617 rows / 11.7% — no work needed)

| Shape | Count | Description |
|---|---:|---|
| `numbered_list` | 1,019 | Has `\n1.`, `\n2.`, `\n3.`, `\n4.` markers |
| `roman_numeral_list` | 548 | Has `\nI.`, `\nII.`, `\nIII.`, `\nIV.` markers |
| `bulleted_list` | 50 | Has `\n- …` or `\n• …` markers |

**Sample (row 6635)**:
```
Which of the following statements regarding Ankylosing spondylitis (AS) are true?
1. AS occurs in about 10 % of Inflammatory Bowel Disease(IBD) patients
2. The AS activity is related to Bowel activity
3. …
```

### ⚠ Inlined / needs work (~469 rows / 3.4%)

#### `roman_numeral_inline` — ~150 rows — **migration 0031**

Statements joined end-to-end on a single line, separated by `I. …II. …III. …` markers.

**Sample (row 19976)** — the most common shape:
```
Which of the following correctly represent the ideal selection criteria for
attempted vaginal breech delivery?
I. Average fetal weight between 1.5 kg and 3.5 kg II. Flexed fetal head
III. Footling presentation with adequate pelvis IV. Zatuchni-Andros score ≥4
Select the correct answer using the code given below:
```

Should become:
```
Which of the following correctly represent the ideal selection criteria for
attempted vaginal breech delivery?
I. Average fetal weight between 1.5 kg and 3.5 kg
II. Flexed fetal head
III. Footling presentation with adequate pelvis
IV. Zatuchni-Andros score ≥4
Select the correct answer using the code given below:
```

#### `code_table_prompt` — ~319 rows — **migration 0032**

Ends with *"Select the correct answer using the code given below:"* — the body has either no list or only a partial list.

**Sample (row 5684)**:
```
Pulmonary stage is seen in which of the following infections?
Ascaris lumbricoides
Strongyloides stercoralis
Onchocerca volvulus
Select the correct answer using the code given below.
```

This is a *display* issue, not a data issue: `option_a..d` are still populated, the user just doesn't see them as a numbered list in the card.

#### `assertion_reason` — 223 rows — **separate (lower priority)**

Standard A/R format: `Assertion (A): … Reason (R): …`. These already render fine on the detail panel because of the parenthetical structure; the issue is purely cosmetic in the card preview.

### ℹ Cosmetic / lower priority (555 rows)

| Shape | Count | Note |
|---|---:|---|
| `image_token_question` | 450 | Has `[[img:N]]`; renders correctly via `resolveImageTokensForMarkdown`. Display verified on detail panel. |
| `mojibake` (false positives) | 32 | These have non-ASCII Latin characters (e.g. `é`, `ü`, `ñ`) that aren't actually mojibake. **Real mojibake codepoints (`Ã©`, `â€™`, `ï»¿`) — 0 rows.** |

### ℹ Normal prose (11,147 rows / 80.8%)

| Shape | Count | Description |
|---|---:|---|
| `long_prose` | 6,885 | Multi-sentence clinical question; stem only. Normal. |
| `short_prose` | 4,262 | One- or two-sentence question. Normal. |

These need no work — they render correctly.

---

## Confirmed Removals (already done by 0027 + 0029 + 0030)

| Shape | Original count | After migrations | Migration |
|---|---:|---:|---|
| `raw_html` (any `<p>`, `<strong>`, `&nbsp;`) | unknown | **0** | 0027 |
| `leaked_correct_incorrect` (`<p>correct</p>` leak) | 129 | **0** | 0029 |
| `inlined_statements` (period-joined multi-statement) | ~99 | **0** | 0030 |
| `trailing_line_correct_incorrect` (`\n…correct$`) | 372 | **0** | 0027 |

---

## Remaining Migration Plan

| # | Migration | Rows expected | Confidence | Risk |
|---|---|---:|---|---|
| **0031** | Roman-numeral inline list split | ~150 | **High** | Low — narrow regex trigger; only fires when row contains true I./II./III. sequence on same line |
| **0032** | Code-table rows: split inlined lists into `1./2./3./4.` markers | ~30–50 of 319 (most are already structured) | Medium | Low–Medium — must preserve question_text meaning |
| **0033** | Mojibake cleanup pass | **0 rows** (skip — no actual mojibake in prod) | n/a | n/a |
| **0034** | Topic classification (11,918 NULL rows) | up to 11,918 | **Lowest** | **High** — needs explicit user approval + per-subject keyword dict |
| **0035** | Structural audit table | 13,788 (read + audit columns only) | High | None — read-only |

---

## 0031 — Roman-Numeral Inline Split (next to ship)

**Trigger condition**: question_text contains two or more consecutive `I. …II. …III. …IV.` markers with no `\n` between them.

**Conservative guard rails**:

1. Only fire when there are at least 3 Roman markers (I, II, III) — filters sentences that incidentally contain "World War II" or "Henry VIII".
2. Roman markers must be at line start (after `\n` OR at the start of `question_text`).
3. Don't fire on rows that already have any `\n- …` or `\n1. …` markers (already structured).
4. Don't fire if the inter-marker content is too short (< 8 chars avg) — filters false positives on lists like *"I. A II. B"* which is already a list.
5. Don't fire on the word `"I"` alone (must be `I.`).

**Reversibility**: forward-only. The reverse migration marks affected rows `needs_review=True` so a human can re-attach the inlined form if needed.

**Dry-run preview** (currently planned, not yet committed):

| ID | Before | After |
|---|---|---|
| 19976 | `…IV. Zatuchni-Andros score ≥4` | `IV. Zatuchni-Andros score ≥4` (with `\n` separators inserted) |
| 20618 | `…IV. Parasitic myoma Select the correct code:` | `…IV. Parasitic myoma\nSelect the correct code:` |

---

## 0032 — Code-Table Normalization (deferred)

**Trigger**: ends with *"Select the correct answer using the code given below:"* and body has at least 2 statements separated by `\n` but no list markers.

**Action**: insert `1. `, `2. `, etc. markers before each statement. (Similar to 0030 but for code-table prompts.)

**Risk**: a small fraction of these rows are intentionally structured as "match the following" exercises where the body is a 2-column table. Need to verify that those aren't in this bucket before writing.

---

## 0033 — MojiB Cleanup — **SKIPPED**

Audit confirmed 0 rows contain classic mojibake codepoints (`Ã©`, `â€™`, `ï»¿`). The 32 rows the simple mojibake detector flagged contain legitimate non-ASCII characters (French, German, etc.). **No migration needed.**

---

## 0034 — Topic Classification — **DEFERRED** (separate session)

Will produce a separate design doc with per-subject keyword dictionary + confidence scoring + human-review queue.

---

## 0035 — Audit Table — **DEFERRED** (low value)

Adding per-row `structural_shape` and `last_audit_at` columns gives ops visibility into future regressions, but no immediate production need.

---

## How to Reproduce the Audit

```bash
cd backend
python scripts/structural_audit_2026_07_28.py
# Output: docs/STRUCTURAL_AUDIT_2026_07_28.json + console summary
```

The audit script is **read-only** — safe to run in production.