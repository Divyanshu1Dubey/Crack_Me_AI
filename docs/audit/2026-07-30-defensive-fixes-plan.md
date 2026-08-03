# Defensive Fixes — 2026-07-30 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the 9 🔴 active bugs + highest-leverage 🟡 risks identified in the spec at [docs/audit/DEFENSIVE_FINDINGS_2026_07_30.md](DEFENSIVE_FINDINGS_2026_07_30.md).

**Architecture:** Mechanical defensive patches across frontend (CSP, a11y, dark-mode) and backend (tombstone guards, IDOR-reducing checks). Each wave is self-contained and revertible via `git revert <SHA>`. No schema, migration, or auth-config changes.

**Tech Stack:** Django 5 + DRF + SimpleJWT; Next.js 16 + React 19 + Tailwind 4; GitHub Actions CI; Vercel + DigitalOcean App Platform hosts.

## Global Constraints

These apply to every task. Violating any one is a failed task.

- **No schema changes**, no new migrations, no `makemigrations` output.
- **No `.env` file or Supabase-config edits.** `.env` lives on the developer machine; not in git.
- **No new top-level directories.** All paths under existing `frontend/`, `backend/`, `docs/`, `.github/`.
- **No SEO copy rewrites** on landing pages `/`, `/cms`, `/neet-pg`, `/inicet`, `/ini-cet`, `/usmle`, `/fmge`. Site-wide copy stays as-is.
- **Preserve all existing comments and docstrings.** Add new comments only above new code.
- **Every commit must leave the tree syntactically valid.** `python manage.py check`, `python -m py_compile`, `npm run lint`, `npx tsc --noEmit`, `npm run build` must all return 0 errors before committing.
- **Per project `CLAUDE.md`**: every change is backwards-compatible. No feature flags for shipped fixes.
- **Commit messages** end with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` per project convention.
- **No live data writes** — content row fix in Task 4 requires human review of fixture diff before applying.

---

## File Structure

Files touched across all tasks. Each task names its subset.

| File | Role |
|---|---|
| `frontend/vercel.json` | CSP `connect-src` allowlist |
| `frontend/src/app/login/LoginClient.tsx` | Login form label/input a11y wiring |
| `frontend/src/app/register/page.tsx` | Register form label/input a11y wiring |
| `frontend/src/components/ui/input.tsx` | Forward `id`/`name` to underlying input element |
| `frontend/src/app/dashboard/page.tsx` | Heatmap "Today" legend color match |
| `frontend/src/components/question/ExamQuestionBank.tsx` | INI-CET practice banner; `<a>` → `<Link>`; `prose` removal; search/dropdown race |
| `frontend/src/app/admin/questions-editor/page.tsx` | Admin editor `dark:` variants |
| `frontend/src/app/admin/questions-editor/QuestionEditModal.tsx` | Modal `dark:` variants |
| `frontend/src/app/dashboard/page.tsx` (read only) | `is_expired` filter on announcements |
| `frontend/src/app/subscription/page.tsx` | Quick-Switch rename |
| `backend/accounts/views.py` | TokenPurchaseView payment gate |
| `backend/questions/views.py` | Tombstone guards on duplicate + perform_create + perform_update + .upload + .import_preview |
| `backend/questions/tests_phase4.py` (NEW tests) | Tombstone guard tests |
| `backend/questions/management/commands/fix_embedded_options.py` (NEW) | One-shot data fix for C1 |
| `backend/{ai_engine,questions,scripts,mce}/**/*{import_*,process_pdfs,vision_extractor,stage_db_writer}.py` | 9 import-script tombstone guards |
| `.github/workflows/ci.yml` | CI gate activation (remove `\|\| true`) |

---

## Wave A: 1-3 line client-side wins

### Task 1: GA4 analytics CSP — add `analytics.google.com` to `connect-src`

**Files:**
- Modify: `frontend/vercel.json:13` (the `connect-src` value inside the CSP header)

**Interfaces:**
- Consumes: existing CSP string.
- Produces: same header value with `https://analytics.google.com` prepended to `connect-src`.

- [ ] **Step 1: Read the existing CSP**

```bash
cat frontend/vercel.json
```
Expected: a JSON object with one `headers` entry whose single header `key` is `Content-Security-Policy` and whose `value` is a single-line CSP string.

- [ ] **Step 2: Edit `connect-src` allowlist**

In `frontend/vercel.json`, locate the `connect-src` portion of the CSP (substring between `connect-src 'self'` and the next semicolon that ends a directive — but the existing CSP uses spaces, find the substring `connect-src 'self' https://crackcms-vsthc.ondigitalocean.app`).

Prepend `https://analytics.google.com ` immediately after `connect-src 'self' ` so it becomes `connect-src 'self' https://analytics.google.com https://crackcms-vsthc.ondigitalocean.app https://crackcms-backend.onrender.com ...`.

Do NOT alter any other directive. Do NOT add newlines.

- [ ] **Step 3: Verify the JSON still parses**

Run: `python -c "import json; print(json.dumps(json.load(open('frontend/vercel.json'))))" | head -50`
Expected: valid JSON output; the CSP value is unchanged in every other respect.

- [ ] **Step 4: Commit**

```bash
git add frontend/vercel.json
git commit -m "fix(csp): allow analytics.google.com to unblock GA4 collect pings

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 5: Verify on live site**

After Vercel auto-deploys (~60 s):
1. Open `https://cracklabs.app/` in Chrome DevTools console.
2. Navigate to `/questions`, `/ai-tutor`.
3. Expected: zero console errors saying "Connecting to ... violates the following Content Security Policy directive".
4. Realistic GA4 collect ping target: `https://www.google-analytics.com/g/collect` (allowed) AND `https://analytics.google.com/g/collect` (now allowed). Both must succeed.

### Task 2: Login form `htmlFor`/`id` wiring

**Files:**
- Modify: `frontend/src/components/ui/input.tsx` (forward `id` to `<input>`)
- Modify: `frontend/src/app/login/LoginClient.tsx` (associate `<label>` to each field)

**Interfaces:**
- Consumes: existing `InputProps`.
- Produces: `<Input id="login-email" ... />` renders an `<input id="login-email">`. `<label htmlFor="login-email">Email</label>` focuses it on click.

- [ ] **Step 1: Read the existing Input component**

```bash
cat frontend/src/components/ui/input.tsx
```
Find the `InputProps` interface and the forwardRef body.

- [ ] **Step 2: Forward `id` through Input**

In `frontend/src/components/ui/input.tsx`, ensure the props being spread to the underlying `<input>` include the forwarded `id`. If the component uses `React.InputHTMLAttributes<HTMLInputElement>`, it already accepts `id`. Confirm by reading 10 lines around the `<input>` tag. If `id` is filtered out, remove it from any `omit` list.

- [ ] **Step 3: Add `id` and `htmlFor` to LoginClient fields**

In `frontend/src/app/login/LoginClient.tsx`, find each form field. There are two: email and password. For each:
- Add `id="login-email"` (or `login-password`) to the `<Input ...>`.
- Change `<label>Email</label>` (or Password) to `<label htmlFor="login-email">Email</label>`.

Pattern (do this twice, once per field):
```tsx
<label htmlFor="login-email" className="...">Email</label>
<Input id="login-email" type="email" ... />
```

- [ ] **Step 4: Run TypeScript check**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS, 0 errors.

- [ ] **Step 5: Browser smoke**

Navigate to `https://cracklabs.app/login`. Click the "Email" label. Expected: the email input gains focus.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ui/input.tsx frontend/src/app/login/LoginClient.tsx
git commit -m "fix(a11y): wire login form labels to inputs (htmlFor/id)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 3: Register form labels — same pattern as Task 2

**Files:**
- Modify: `frontend/src/app/register/page.tsx` (six fields: First Name, Last Name, Username, Email, Password, Confirm Password)

**Interfaces:**
- Same as Task 2.

- [ ] **Step 1: Read register form**

```bash
grep -n "htmlFor\|<label" frontend/src/app/register/page.tsx
```
Find the 6 label/input pairs.

- [ ] **Step 2: Apply the wiring pattern to all 6 fields**

For each field, add unique `id="register-{fieldname}"` to the `<Input>` and matching `htmlFor="register-{fieldname}"` to the `<label>`.

Field IDs (use these exact strings):
- `register-first-name`
- `register-last-name`
- `register-username`
- `register-email`
- `register-password`
- `register-confirm-password`

- [ ] **Step 3: TypeScript check**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS.

- [ ] **Step 4: Browser smoke**

Navigate to `https://cracklabs.app/register`. Click each label — focus must move to the matching input.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/register/page.tsx
git commit -m "fix(a11y): wire register form labels to inputs (6 fields)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 4: Dashboard heatmap "Today" legend color match

**Files:**
- Modify: `frontend/src/app/dashboard/page.tsx:619` and `:632`

**Interfaces:**
- Find the today-cell `<div>` with `ring-sky-500` and the legend swatch with `ring-blue-500`.

- [ ] **Step 1: Confirm both classes exist**

```bash
sed -n '619p;632p' frontend/src/app/dashboard/page.tsx
```
Both lines should show either `ring-sky-500` (cell) or `ring-blue-500` (legend).

- [ ] **Step 2: Pick `sky-500` as the canonical ring and align both**

Replace `ring-blue-500` with `ring-sky-500` in the legend line. Use `Edit` with `replace_all=false` and the unique surrounding context.

- [ ] **Step 3: Visual smoke**

Run `cd frontend && npm run build` — should succeed. (Live preview deferred to next deploy.)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/dashboard/page.tsx
git commit -m "fix(dashboard): align heatmap 'Today' legend with today-cell ring color

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 5: INI-CET Practice Fullscreen → warn when slug falls back to CMS

**Files:**
- Modify: `frontend/src/components/question/ExamQuestionBank.tsx:651-666` and `frontend/src/app/questions/practice/page.tsx`

**Interfaces:**
- Consumes: practice-page slug map at `frontend/src/app/questions/practice/page.tsx:46-49`.
- Produces: a warning banner shown when the slug falls back to a different exam.

- [ ] **Step 1: Read the slug map**

```bash
sed -n '46,49p' frontend/src/app/questions/practice/page.tsx
```
Expected: `PRACTICE_SLUG_TO_EXAM_TYPE` with `ini-cet` → `cms`, `inicet` → `cms`, `medical-officer` → `cms`. These three are the fallbacks.

- [ ] **Step 2: In the practice page, surface a fallback warning**

In `frontend/src/app/questions/practice/page.tsx`, after the slug-to-exam-type resolution in `PracticeContent`, add a `useMemo` that detects `slug` is set but the resolved `examType` doesn't match a known track. Concretely, after the `practiceSlugToExamType(...)` call, compute:

```tsx
const isSlugFallback = slug && (
    slug === 'ini-cet' || slug === 'inicet' || slug === 'medical-officer'
);
```

Render a yellow `<Card>` at the top of the page (inside the existing `<Suspense>` children) when `isSlugFallback` is true:

```tsx
{isSlugFallback && (
    <Card className="m-4 border-amber-300 bg-amber-50 dark:bg-amber-900/20">
        <CardContent className="py-3 text-sm text-amber-900 dark:text-amber-100">
            Practice session for <strong>{slug}</strong> isn't yet populated in our bank.
            Showing <strong>{examType?.toUpperCase()}</strong> questions as a fallback. INI-CET tracks ship in a future release.
        </CardContent>
    </Card>
)}
```

Use the existing `Card`, `CardContent` imports from `@/components/ui/card` (already imported in this file).

- [ ] **Step 3: TypeScript check**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS.

- [ ] **Step 4: Browser smoke (after deploy)**

1. On `cracklabs.app/questions`, select INI-CET exam track.
2. Click "Practice Fullscreen".
3. Expected: yellow banner explains questions shown are CMS, not INI-CET.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/questions/practice/page.tsx
git commit -m "fix(practice): show fallback banner when slug maps to a different exam

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Wave B: Critical backend safety fixes

### Task 6: Tombstone guard on `QuestionViewSet.duplicate`

**Files:**
- Modify: `backend/questions/views.py:2013-2054`

**Interfaces:**
- Consumes: helper `pre_check_create(text, where=...)` at `backend/questions/import_protection.py:54-69`.
- Produces: 409 Conflict response when an admin tries to duplicate a previously-removed question.

- [ ] **Step 1: Read the duplicate action**

```bash
sed -n '2013,2054p' backend/questions/views.py
```

- [ ] **Step 2: Write a failing test**

Add to `backend/questions/tests_phase4.py` (or appropriate tests file):

```python
def test_duplicate_skips_removed_question(self):
    from questions.models import RemovedQuestion, compute_stem_hash
    q = Question.objects.create(
        question_text='Original stem',
        option_a='A', option_b='B', option_c='C', option_d='D',
        correct_answer='A', year=2024,
    )
    RemovedQuestion.objects.create(
        question_text_hash=compute_stem_hash(q.question_text),
        removed_by=self.user, reason='admin removed',
    )
    self.client.force_authenticate(user=self.admin)
    res = self.client.post(f'/api/questions/{q.id}/duplicate/')
    self.assertEqual(res.status_code, 409)
    self.assertIn('previously-removed', res.json()['error'])
```

- [ ] **Step 3: Run test — verify it fails**

Run: `cd backend && python manage.py test questions.tests_phase4 -v 2`
Expected: FAIL with `AttributeError` or `200 != 409`.

- [ ] **Step 4: Add the guard**

At the top of `duplicate()` (after `question = self.get_object()`), add:

```python
if _pre_check_remove(question.question_text, 'questions.views.duplicate'):
    return Response(
        {'error': 'Stem matches a previously-removed question; un-remove first.'},
        status=status.HTTP_409_CONFLICT,
    )
```

The alias `_pre_check_remove` is already imported at `views.py:48` (`from .import_protection import pre_check_create as _pre_check_remove`) and used at `views.py:1358`. Reuse it to keep naming consistent.

- [ ] **Step 5: Run test — verify it passes**

Run: `cd backend && python manage.py test questions.tests_phase4 -v 2`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/questions/views.py backend/questions/tests_phase4.py
git commit -m "fix(questions): honor RemovedQuestion tombstone on duplicate action

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 7: Tombstone guard on `QuestionViewSet.perform_create` and `perform_update`

**Files:**
- Modify: `backend/questions/views.py:2188-2201`

**Interfaces:**
- Consumes: `serializer.validated_data`, `request`, helper `pre_check_create`.
- Produces: 409 Conflict when an admin creates or updates a question to text matching a tombstone.

- [ ] **Step 1: Read perform_create/perform_update**

```bash
sed -n '2188,2201p' backend/questions/views.py
```

- [ ] **Step 2: Write failing tests**

Add to `backend/questions/tests_phase4.py`:

```python
def test_create_skips_removed_question(self):
    from questions.models import RemovedQuestion, compute_stem_hash
    RemovedQuestion.objects.create(
        question_text_hash=compute_stem_hash('Banned stem'),
        removed_by=self.user, reason='admin removed',
    )
    self.client.force_authenticate(user=self.admin)
    res = self.client.post('/api/questions/', {
        'question_text': 'Banned stem',
        'option_a': 'A', 'option_b': 'B', 'option_c': 'C', 'option_d': 'D',
        'correct_answer': 'A', 'year': 2024,
    }, format='json')
    self.assertEqual(res.status_code, 409)

def test_update_skips_removed_question(self):
    # Create a tombstone and a question, then try to PATCH the question text to the tombstone stem.
    from questions.models import RemovedQuestion, compute_stem_hash
    RemovedQuestion.objects.create(
        question_text_hash=compute_stem_hash('Banned stem'),
        removed_by=self.user, reason='admin removed',
    )
    q = Question.objects.create(
        question_text='OK stem', option_a='A', option_b='B',
        option_c='C', option_d='D', correct_answer='A', year=2024,
    )
    self.client.force_authenticate(user=self.admin)
    res = self.client.patch(f'/api/questions/{q.id}/', {'question_text': 'Banned stem'}, format='json')
    self.assertEqual(res.status_code, 409)
```

- [ ] **Step 3: Run tests — verify they fail**

Run: `cd backend && python manage.py test questions.tests_phase4 -v 2`
Expected: FAIL with 201/200 (the success path).

- [ ] **Step 4: Add guards**

Replace `perform_create` and `perform_update`:

```python
def perform_create(self, serializer):
    text = serializer.validated_data.get('question_text', '')
    if _pre_check_remove(text, 'questions.views.perform_create'):
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied('Stem matches a previously-removed question; un-remove first.')
    serializer.save()

def perform_update(self, serializer):
    text = serializer.validated_data.get('question_text', None)
    if text is not None and _pre_check_remove(text, 'questions.views.perform_update'):
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied('Stem matches a previously-removed question; un-remove first.')
    serializer.save()
```

(Using `_pre_check_remove` alias from `views.py:48`; same pattern as Task 6.)

- [ ] **Step 5: Run tests — verify they pass**

Run: `cd backend && python manage.py test questions.tests_phase4 -v 2`
Expected: 3 tombstone tests PASS (the 2 new ones + Task 6).

- [ ] **Step 6: Also wire the `.upload` (line 921) and `.import_preview` (line 1015) actions**

In each, before `serializer.save()`:
```python
if _pre_check_remove(item.question_text, 'questions.views.upload'):
    return Response({'error': 'Stem matches a previously-removed question; un-remove first.'}, status=status.HTTP_409_CONFLICT)
```

(Use `where='questions.views.import_preview'` for the other.)

- [ ] **Step 7: Run full QuestionViewSet tests**

Run: `cd backend && python manage.py test questions --verbosity=2`
Expected: PASS, no regressions.

- [ ] **Step 8: Commit**

```bash
git add backend/questions/views.py backend/questions/tests_phase4.py
git commit -m "fix(questions): honor RemovedQuestion tombstone on create/update/upload/import_preview

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 8: Block `TokenPurchaseView` until real payment verified

**Files:**
- Modify: `backend/accounts/views.py:745-781`
- Modify: `backend/accounts/models.py` (add `payment_verified_at` field on a new `TokenPurchase` model — see step 4)

**Interfaces:**
- Consumes: `request.user`, `TokenConfig.get_config()`, `Razorpay` SDK.
- Produces: 402 Payment Required (or 503 Service Unavailable if Razorpay isn't configured) on every call to `/api/auth/tokens/purchase/`.

- [ ] **Step 1: Read TokenPurchaseView verbatim**

```bash
sed -n '745,795p' backend/accounts/views.py
```

- [ ] **Step 2: Refuse all token credits that lack payment verification**

Replace `TokenPurchaseView.post` with a guard:

```python
def post(self, request):
    # Token purchase requires a verified Razorpay payment. Until the
    # gateway integration is wired up (see Wave B token economy refactor),
    # we refuse all credit to prevent the throttle-only bounty on
    # unlimited token minting.
    from rest_framework.exceptions import APIException
    class TokenPurchasePendingGateway(Exception):
        status_code = 503
        default_detail = 'Token purchase is temporarily disabled while the payment gateway integration is being finalized.'
        default_code = 'service_unavailable'
    raise TokenPurchasePendingGateway()
```

- [ ] **Step 3: Update docstring**

```python
class TokenPurchaseView(APIView):
    """POST: Disabled until Razorpay checkout is integrated (issue #NUM).
    
    POSTs return 503. UI should route the user to /subscription or
    await the Razorpay-backed release before retrying.
    """
```

- [ ] **Step 4: Write a test that confirms a stray POST is refused**

```python
def test_token_purchase_disabled(self):
    self.client.force_authenticate(user=self.user)
    res = self.client.post('/api/auth/tokens/purchase/', {'amount': 100, 'payment_id': 'fake'}, format='json')
    self.assertEqual(res.status_code, 503)
```

Add to `backend/accounts/tests.py` (create a new test class if file lacks one).

- [ ] **Step 5: Run test — verify it fails first**

Run: `cd backend && python manage.py test accounts -v 2 -k test_token_purchase_disabled`
Expected: FAIL with `200` status, before step 2.

- [ ] **Step 6: Apply step 2 fix**

(re-do step 2.)

- [ ] **Step 7: Run test — verify it passes**

Run: `cd backend && python manage.py test accounts -v 2 -k test_token_purchase_disabled`
Expected: PASS.

- [ ] **Step 8: Update frontend `/tokens` page to show "Buy tokens coming soon"**

In `frontend/src/app/tokens/page.tsx`, find the `handlePurchase` callback and the buy-tokens button. Wrap the button in a disabled state:

```tsx
<Button
  type="button"
  disabled
  title="Token purchases are temporarily unavailable — payment gateway integration in progress."
  className="..."
>
  Buy tokens (temporarily unavailable)
</Button>
```

Add a small `<p className="text-xs text-muted-foreground mt-2">` below explaining the temporary nature.

- [ ] **Step 9: Lint + typecheck**

Run: `cd frontend && npm run lint && npx tsc --noEmit`
Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add backend/accounts/views.py backend/accounts/tests.py frontend/src/app/tokens/page.tsx
git commit -m "fix(tokens): disable TokenPurchaseView until Razorpay checkout is wired up

Mints tokens without payment verification were possible behind the throttle.
Defensive 503 + UI banner until the gateway integration ships.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Wave C: Import script tombstone guards (mechanical)

### Task 9: 9-line × 9-file `pre_check_create` sweep

**Files:**
- Modify: `backend/ai_engine/management/commands/process_pdfs.py:87`
- Modify: `backend/ai_engine/management/commands/import_txt.py:106`
- Modify: `backend/ai_engine/management/commands/import_pyq_pdfs.py:128`
- Modify: `backend/scripts/vision_extractor.py:120`
- Modify: `backend/mce/stages/stage_db_writer.py:231`
- Modify: `backend/questions/management/commands/import_pyqs.py:188`
- Modify: `backend/questions/management/commands/import_mocktests.py:908`
- Modify: `backend/questions/management/commands/import_2025_pyqs.py:138`
- Modify: `backend/questions/management/commands/import_2023_2024_pyqs.py:140`
- Modify: `backend/questions/management/commands/import_2018_2019_pyqs.py:143`

**Skip per helper docstring:**
- `backend/questions/management/commands/load_exam_fixture.py:509` (already caches RemovedQuestion once per run)
- `backend/questions/management/commands/import_neet_pg.py:248` (already uses `is_removed` via `_save_questions`)

- [ ] **Step 1: For each file, read ~10 lines around the `Question.objects.create(...)` call**

```bash
for f in backend/ai_engine/management/commands/process_pdfs.py backend/ai_engine/management/commands/import_txt.py backend/ai_engine/management/commands/import_pyq_pdfs.py backend/scripts/vision_extractor.py backend/mce/stages/stage_db_writer.py backend/questions/management/commands/import_pyqs.py backend/questions/management/commands/import_mocktests.py backend/questions/management/commands/import_2025_pyqs.py backend/questions/management/commands/import_2023_2024_pyqs.py backend/questions/management/commands/import_2018_2019_pyqs.py; do
  echo "=== $f ==="
  grep -n "Question.objects.create" "$f" || true
done
```

- [ ] **Step 2: For each file, add the import**

At the file's import block, ensure:
```python
from questions.import_protection import pre_check_create
```

If the file is `backend/ai_engine/...` or `backend/mce/...` or `backend/scripts/...`, `questions` is a sibling app. Verify by:
```bash
python -c "from questions.import_protection import pre_check_create" --directory backend
```
If the import path needs adjustment (rare), fall back to `from questions import import_protection as _ip; pre_check_create = _ip.pre_check_create`.

- [ ] **Step 3: Per-file: add `pre_check_create` guard immediately before `Question.objects.create(...)`**

Pattern (substitute the `where=` label per file):
```python
if pre_check_create(stem_text, where='commands.process_pdfs'):
    continue
```

Replace `continue` with `pass` or `return` if the surrounding control flow isn't a loop.

Field-label map (use these exact `where=` strings):
| File | `where=` |
|---|---|
| `process_pdfs.py` | `'commands.process_pdfs'` |
| `import_txt.py` | `'commands.import_txt'` |
| `import_pyq_pdfs.py` | `'commands.import_pyq_pdfs'` |
| `vision_extractor.py` | `'scripts.vision_extractor'` |
| `stage_db_writer.py` | `'mce.stage_db_writer'` |
| `import_pyqs.py` | `'commands.import_pyqs'` |
| `import_mocktests.py` | `'commands.import_mocktests'` |
| `import_2025_pyqs.py` | `'commands.import_2025_pyqs'` |
| `import_2023_2024_pyqs.py` | `'commands.import_2023_2024_pyqs'` |
| `import_2018_2019_pyqs.py` | `'commands.import_2018_2019_pyqs'` |

The variable holding the question text differs per file (`text`, `question_text`, `q['question_text']`, etc.). Inspect each and pass the same value to `pre_check_create` that will be passed to `Question.objects.create(question_text=…)`.

- [ ] **Step 4: Per-file compile check**

```bash
python -m py_compile backend/ai_engine/management/commands/process_pdfs.py
python -m py_compile backend/ai_engine/management/commands/import_txt.py
python -m py_compile backend/ai_engine/management/commands/import_pyq_pdfs.py
python -m py_compile backend/scripts/vision_extractor.py
python -m py_compile backend/mce/stages/stage_db_writer.py
python -m py_compile backend/questions/management/commands/import_pyqs.py
python -m py_compile backend/questions/management/commands/import_mocktests.py
python -m py_compile backend/questions/management/commands/import_2025_pyqs.py
python -m py_compile backend/questions/management/commands/import_2023_2024_pyqs.py
python -m py_compile backend/questions/management/commands/import_2018_2019_pyqs.py
```
Expected: each command exits 0 silently.

- [ ] **Step 5: Run `manage.py check`**

Run: `cd backend && python manage.py check`
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 6: Single combined commit**

```bash
git add backend/ai_engine/management/commands/process_pdfs.py \
        backend/ai_engine/management/commands/import_txt.py \
        backend/ai_engine/management/commands/import_pyq_pdfs.py \
        backend/scripts/vision_extractor.py \
        backend/mce/stages/stage_db_writer.py \
        backend/questions/management/commands/import_pyqs.py \
        backend/questions/management/commands/import_mocktests.py \
        backend/questions/management/commands/import_2025_pyqs.py \
        backend/questions/management/commands/import_2023_2024_pyqs.py \
        backend/questions/management/commands/import_2018_2019_pyqs.py
git commit -m "fix(importers): honor RemovedQuestion tombstone in 10 import paths

Mechanical 3-line guard (import + pre-check + skip) across every
Question.objects.create(...) site that wasn't already covered by
load_exam_fixture or import_neet_pg.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Wave D: CI gate activation

### Task 10: Remove `|| true` from deploy-safety and security gates

**Files:**
- Modify: `.github/workflows/ci.yml:25, 70-72`

**Interfaces:**
- Consumes: existing CI commands.
- Produces: same commands that now fail the job when they detect a real issue.

- [ ] **Step 1: Read the current CI workflow**

```bash
sed -n '20,35p;65,75p' .github/workflows/ci.yml
```

- [ ] **Step 2: Drop `|| true` from `manage.py check --deploy`**

Find: `python manage.py check --deploy 2>&1 || true`
Replace: `python manage.py check --deploy 2>&1`
Justification: This is a deploy-safety check. Failing it must block deploy.

- [ ] **Step 3: Drop `|| true` from bandit (after the first invocation)**

Find lines that start with `bandit -r backend/` and end with `|| true`.
Replace the second/third such lines (visual snapshots and live-audit remain `|| true` since they are warning-only by design).

Concretely: keep `|| true` only on:
- `bandit` first invocation if explicitly marked "informational"
- visual snapshot job (line ~104) — pixel diffs are noisy
- live-audit job (line ~141) — depends on flaky live site

Drop `|| true` from:
- `python manage.py check --deploy`
- `bandit -r backend/` (the second invocation that uploads results)

- [ ] **Step 4: Verify CI file still parses**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"` from repo root.
Expected: valid YAML.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: fail the job on deploy-safety check + bandit findings

Was masking deploy regressions behind || true. Visual snapshots and
live-audit remain warning-only (flaky by nature).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Wave E: Admin dark-mode re-skin

### Task 11: Add `dark:` variants to admin questions-editor surfaces

**Files:**
- Modify: `frontend/src/app/admin/questions-editor/page.tsx:396-871` (20 occurrences)
- Modify: `frontend/src/app/admin/questions-editor/QuestionEditModal.tsx:194-519` (8 occurrences)

**Interfaces:**
- Consumes: existing class strings like `bg-white text-gray-900 border-gray-300 placeholder-gray-400`.
- Produces: same string with `dark:bg-slate-900 dark:text-slate-100 dark:border-slate-700 dark:placeholder-slate-500` appended.

- [ ] **Step 1: Find every `bg-white` in the editor**

```bash
grep -n "bg-white\|text-gray-900\|placeholder-gray-400\|border-gray-300" frontend/src/app/admin/questions-editor/page.tsx frontend/src/app/admin/questions-editor/QuestionEditModal.tsx
```

- [ ] **Step 2: For each line, append the `dark:` variants**

For `bg-white` → `bg-white dark:bg-slate-900`
For `text-gray-900` → `text-gray-900 dark:text-slate-100`
For `border-gray-300` → `border-gray-300 dark:border-slate-700`
For `placeholder-gray-400` → `placeholder-gray-400 dark:placeholder-slate-500`

Replace per-line with `Edit` and verify the diff is only additive (`dark:` variants added, never class removed).

- [ ] **Step 3: Lint + typecheck**

Run: `cd frontend && npm run lint && npx tsc --noEmit`
Expected: PASS, no new warnings.

- [ ] **Step 4: Visual smoke (after deploy)**

In dev mode with `dark` class set on `<html>`:
1. Open `/admin/questions-editor`.
2. Expected: form inputs read on slate-900 background; text is legible.
3. Repeat for the modal opened by clicking any row.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/admin/questions-editor/page.tsx frontend/src/app/admin/questions-editor/QuestionEditModal.tsx
git commit -m "fix(admin): add dark-mode classes to questions-editor forms

Was rendering white-on-black text in dark mode (20 + 8 sites).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Wave F: Content data fix (with human review gate)

### Task 12: Repair 6 embedded-options questions (spec finding C1)

**Files:**
- Modify: `backend/fixtures/cms_fixture.json` (6 rows in pk 6359-6438)
- Create: `backend/questions/management/commands/fix_embedded_options.py` (one-shot management command; idempotent)

**Interfaces:**
- Consumes: Question rows where `option_a` AND `option_b` AND `option_c` AND `option_d` are all blank AND `question_text` has ≥4 trailing short lines.
- Produces: those rows with the trailing 4 lines moved into `option_a..d` and a stripped stem.

- [ ] **Step 1: Read the management-command directory**

```bash
ls backend/questions/management/commands/
```

- [ ] **Step 2: Create the management command**

Create `backend/questions/management/commands/fix_embedded_options.py`:

```python
"""
fix_embedded_options — One-shot data fix for the 2026-07-30 parser bug
where 6 questions in cms_fixture.json pk 6359..6438 have their options
embedded into question_text and option_a..d blank.

DRY-RUN by default. Pass --apply to commit the change.

Idempotent: rows with non-blank option_a are skipped.

Usage:
    python manage.py fix_embedded_options              # dry-run
    python manage.py fix_embedded_options --apply      # commit
"""
from django.core.management.base import BaseCommand
from questions.models import Question


class Command(BaseCommand):
    help = "Repair questions whose options are embedded into question_text."

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Commit changes (default: dry-run).')
        parser.add_argument('--pks', type=int, nargs='*', help='Restrict to these Question pks.')

    def handle(self, *args, apply=False, pks=None, **options):
        qs = Question.objects.filter(option_a='', option_b='')
        if pks:
            qs = qs.filter(pk__in=pks)
        else:
            qs = qs.filter(pk__in=[6359, 6366, 6418, 6436, 6437, 6438])

        fixed = 0
        for q in qs:
            lines = [l.strip() for l in (q.question_text or '').split('\n') if l.strip()]
            if len(lines) < 5:
                continue
            stem, opts = lines[:-4], lines[-4:]
            if not all(3 <= len(o) <= 80 for o in opts):
                continue
            self.stdout.write(f'pk={q.pk}  stem={lines[0][:80]!r}  opts={opts}')
            if apply:
                q.question_text = '\n'.join(stem).rstrip(': \n') + '?'
                q.option_a, q.option_b, q.option_c, q.option_d = opts
                q.save(update_fields=['question_text', 'option_a', 'option_b', 'option_c', 'option_d'])
                fixed += 1
        verb = 'Fixed' if apply else 'Would fix'
        self.stdout.write(self.style.SUCCESS(f'{verb} {fixed} question(s).'))
```

- [ ] **Step 3: Dry-run the command**

Run: `cd backend && python manage.py fix_embedded_options`
Expected: lists the 6 rows with their stems + proposed options; reports "Would fix 6 question(s)."

- [ ] **Step 4: HUMAN REVIEW GATE — Stop and ask the user before applying**

Show the dry-run output. Ask the user to confirm `--apply`. Do not proceed without explicit approval because this is the only task that touches live DB rows.

- [ ] **Step 5: After user approval, apply**

Run: `cd backend && python manage.py fix_embedded_options --apply`
Expected: "Fixed 6 question(s)."

- [ ] **Step 6: Re-export fixture**

Run: `cd backend && python manage.py dumpdata questions.Question --indent 2 > backend/fixtures/cms_fixture.json`
Expected: the 6 rows in the fixture now have non-blank `option_a..d` and a clean stem.

(Verify with: `python -c "import json; data=json.load(open('backend/fixtures/cms_fixture.json')); bad=[r for r in data if r['pk'] in {6359,6366,6418,6436,6437,6438} and not r['fields'].get('option_a')]; print('still blank:', len(bad))"` → should print 0.)

- [ ] **Step 7: Commit**

```bash
git add backend/questions/management/commands/fix_embedded_options.py backend/fixtures/cms_fixture.json
git commit -m "fix(questions): repair 6 embedded-options questions (pk 6359-6438)

Parser stuffed options into question_text; option_a..d blank.
Management command is dry-run by default; one-shot. Per-user approval
gathered before --apply per Wave F human review gate.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Wave G: UX polish (lower priority, optional)

> These tasks are puntable to a follow-up session. They're listed so future agents have the recipes, but they're not required for this plan's commits.

### Task 13: Subscription Quick-Switch rename

**Files:**
- Modify: `frontend/src/app/subscription/page.tsx:920`

- [ ] **Step 1: Locate the Quick-Switch button**

```bash
sed -n '900,940p' frontend/src/app/subscription/page.tsx
```

- [ ] **Step 2: Rename and add warning**

Change the button label from "Quick Switch" → "Add Another Period" with a `title` tooltip explaining the additive billing semantics.

### Task 14: Announcements `is_expired` filter

**Files:**
- Modify: `frontend/src/app/dashboard/page.tsx:352-371`

- [ ] **Step 1: Read announcement rendering**

```bash
sed -n '350,375p' frontend/src/app/dashboard/page.tsx
```

- [ ] **Step 2: Filter by `expires_at`**

Insert above the `.slice(0, 3)`:
```ts
const visible = announcements.filter(a => !a.expires_at || new Date(a.expires_at) > new Date());
```
Then use `visible.slice(0, 3)` instead.

### Task 15: `<a>` → `<Link>` in token-exhausted banner

**Files:**
- Modify: `frontend/src/components/question/ExamQuestionBank.tsx:1433`

- [ ] **Step 1: Locate and replace**

Replace `<a href="/tokens" ...>` with `<Link href="/tokens" ...>`. Add `import Link from 'next/link'` if not present.

### Task 16: Remove `prose prose-sm` from AI fallback

**Files:**
- Modify: `frontend/src/components/question/ExamQuestionBank.tsx:1485`

- [ ] **Step 1: Find the prose usage**

```bash
grep -n "prose" frontend/src/components/question/ExamQuestionBank.tsx
```

- [ ] **Step 2: Strip `prose prose-sm`**

Either remove the class string entirely (file's own deprecation comment says so) or replace with `text-sm leading-relaxed whitespace-pre-line`. The latter keeps readability.

---

## Final Smoke Checklist (run after all committed tasks)

- [ ] `cd backend && python manage.py check && python manage.py makemigrations --check --dry-run && python manage.py test --verbosity=2`
- [ ] `cd frontend && npm run lint && npx tsc --noEmit && npm run build`
- [ ] `git log --oneline -10` shows the new commits in order (Tasks 1-12)
- [ ] Live at `cracklabs.app/`: zero CSP errors on every navigation
- [ ] `/admin/login` then `/admin/questions-editor` in dark mode = no white surfaces
- [ ] Token purchase button shows the "temporarily unavailable" disabled state
- [ ] The 6 question fixes are visible in the live bank (filter pk 6359-6438)

## Spec Coverage

| Spec finding | Covered by task |
|---|---|
| L1 (GA CSP) | Task 1 |
| L2 (missing image files) | Out of scope per constraint (live data) |
| F1 (admin dark-mode) | Task 11 |
| F2 (login a11y) | Task 2 |
| F3 (dashboard heatmap color) | Task 4 |
| F4 (INI-CET practice slug) | Task 5 |
| F5 (Quick-Switch semantics) | Task 13 |
| F6 (announcements is_expired) | Task 14 |
| F7 (search/dropdown race) | Punt — needs broader UX rework |
| F8 (prose removal) | Task 16 |
| F9 (lint warning) | Punt — false-positive risk low |
| B1 (duplicate tombstone) | Task 6 |
| B2 (perform_create/update tombstone) | Task 7 |
| B3 (TokenPurchaseView) | Task 8 |
| B4 (AnalyticsIngestView size) | Punt — separate session |
| B5 (DiscussionVote race) | Punt |
| B6 (VerifyScholarshipView brute) | Punt |
| B7 (AIStatusView property/permissions) | Punt |
| B8 (QuestionImageServeView path) | Punt |
| B9 (admin throttle_scope) | Punt |
| I1 (9 import scripts) | Task 9 |
| I2 (CI \|\| true) | Task 10 |
| I3 (import_neet_pg every deploy) | Punt — separate session |
| I4 (EmbeddingIndexer 2000-cap) | Punt |
| I5 (CSP unsafe-inline/eval) | Punt — known cost of Tailwind 4 |
| I7 (6011 images committed) | Punt |
| I9 (Capacitor cleartext) | Punt |
| C1 (6 embedded-options rows) | Task 12 |
| C2 (480 missing_correct_answer) | Punt |
| C3 (RAG staleness) | Punt |
| C4 (6011 images) | see I7 |
| C5 (image files missing) | see L2 |

Twelve tasks ship in this plan. Eight findings punted to follow-up sessions per scope constraints (no live data, no auth-touching changes). Every punted item has a clear handoff location in `LOW_PRIORITY_FIXES.md` or the spec's own "Lower priority follow-ups" section.
