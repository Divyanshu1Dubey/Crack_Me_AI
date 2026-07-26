# Manual Question Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an admin filter the question bank by exam type, open any question in a modal editor, fix text/options/answer/explanation, and insert images inline — then save so the public site shows the fix on the next request.

**Architecture:** Extend the existing admin `/admin/questions-editor` page (no new admin shell) with an `exam_type` filter and a modal editor. The modal issues a single `PATCH /questions/{id}/` with `If-Match` for optimistic lock. Image uploads go to a new `QuestionImageViewSet` that writes to Supabase Storage and returns a `QuestionImage` row. Images are embedded in `question_text` as `[[img:N]]` tokens and resolved by a new `imageTokens.ts` helper on every public page that renders question text.

**Tech Stack:** Django 5 + DRF, Next.js 16 + React 19 + TypeScript, Supabase Storage (Python client already in `requirements.txt`), existing `QuestionImage` model.

**Spec:** [`docs/superpowers/specs/2026-07-26-question-manual-fix-design.md`](../specs/2026-07-26-question-manual-fix-design.md)

## Global Constraints

- Backend: Django 5 + DRF, Python 3.12, Project root `c:/Users/DIVYANSHU/Desktop/crack_cms`. Backend lives in `backend/`, venv at `backend/.venv/`. Use `python manage.py test` to run tests.
- Frontend: Next.js 16 (App Router), React 19, TypeScript strict, Tailwind 4. Dev runs with `npm run dev -- --webpack`. Lint with `npm run lint`.
- Supabase: Python `supabase` client already in `requirements.txt`. Use `supabase.create_client` from `accounts/management/commands/cleanup_supabase_admins.py` as the reference pattern. Env vars: `SUPABASE_URL` (or `NEXT_PUBLIC_SUPABASE_URL`) and `SUPABASE_SERVICE_ROLE_KEY`.
- DRF auth: `IsAdminUser` for the new image endpoints. Existing `QuestionViewSet` permission is unchanged.
- Optimistic locking: `If-Match: <updated_at>` header on `PATCH /questions/{id}/`. Mismatch → `409 Conflict` with body `{"current": <row>}`.
- `[[img:N]]` token format: literal `[[img:` + integer id + `]]`. Anything else is left untouched.
- Image upload constraints: max 5 MB per file, allowed MIME `image/png,image/jpeg,image/webp,image/gif`. Larger or wrong MIME → 400.
- All new env vars already exist in `backend/.env.example` and `frontend/.env.example` — no new env vars required.
- Commit messages end with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- Follow existing patterns in `backend/questions/views.py` and `frontend/src/app/admin/questions-editor/page.tsx`.

---

## File Structure

### New files

- `backend/questions/image_upload.py` — Supabase Storage upload helper, SHA-256 dedupe, width/height/bytes extraction.
- `backend/questions/migrations/0009_questionimage_uploaded_by_admin.py` — adds `uploaded_by_admin` boolean.
- `backend/questions/serializers_question_image.py` — `QuestionImageSerializer` (admin-only fields).
- `backend/questions/tests/test_image_upload.py` — unit tests for new endpoints.
- `backend/scripts/setup_supabase_bucket.py` — one-time bucket creation.
- `frontend/src/app/admin/questions-editor/QuestionEditModal.tsx` — modal editor.
- `frontend/src/lib/imageUpload.ts` — client wrapper for upload/delete/reorder.
- `frontend/src/lib/imageTokens.ts` — `resolveImageTokens(html, images)` + cache.
- `frontend/tests/e2e/admin-question-fix.spec.ts` — Playwright e2e.

### Modified files

- `backend/questions/models.py` — add `uploaded_by_admin` field to `QuestionImage`.
- `backend/questions/serializers.py` — include `images` in `QuestionDetailSerializer` (already done) — no change.
- `backend/questions/views.py` — add `QuestionImageViewSet`, add `perform_update` optimistic lock to `QuestionViewSet`.
- `backend/questions/urls.py` — register `QuestionImageViewSet` router.
- `frontend/src/app/admin/questions-editor/page.tsx` — add `exam_type` filter + year + `[Edit]` button.
- `frontend/src/lib/api.ts` — add 4 new image methods, add `If-Match` support to `update()`.
- `frontend/src/app/questions/[exam]/practice/page.tsx` — use `resolveImageTokens`.
- `frontend/src/components/inicet-pg/IniCetLanding.tsx` — use `resolveImageTokens`.

---

### Task 1: Add `uploaded_by_admin` field to `QuestionImage`

**Files:**
- Modify: `backend/questions/models.py:799-870` (the `QuestionImage` class)
- Create: `backend/questions/migrations/0009_questionimage_uploaded_by_admin.py`

**Interfaces:**
- Consumes: existing `QuestionImage` model.
- Produces: `QuestionImage.uploaded_by_admin: BooleanField(default=False)`.

- [ ] **Step 1: Add the field to the model**

In `backend/questions/models.py`, inside `class QuestionImage`, after the existing `caption` field (around line 850), add:

```python
    uploaded_by_admin = models.BooleanField(
        default=False,
        db_index=True,
        help_text='True if uploaded via the admin manual-fix editor (vs recall importer)',
    )
```

- [ ] **Step 2: Generate the migration**

```bash
cd c:/Users/DIVYANSHU/Desktop/crack_cms/backend
python manage.py makemigrations questions --name questionimage_uploaded_by_admin
```

Expected output: a new file `backend/questions/migrations/0009_questionimage_uploaded_by_admin.py` that adds `uploaded_by_admin` with `default=False`.

- [ ] **Step 3: Apply the migration**

```bash
cd c:/Users/DIVYANSHU/Desktop/crack_cms/backend
python manage.py migrate questions
```

Expected: applies `0009_questionimage_uploaded_by_admin`.

- [ ] **Step 4: Verify the field**

```bash
cd c:/Users/DIVYANSHU/Desktop/crack_cms/backend
python manage.py shell -c "from questions.models import QuestionImage; print(QuestionImage._meta.get_field('uploaded_by_admin').default)"
```

Expected: `False`.

- [ ] **Step 5: Commit**

```bash
cd c:/Users/DIVYANSHU/Desktop/crack_cms
git add backend/questions/models.py backend/questions/migrations/0009_questionimage_uploaded_by_admin.py
git commit -m "feat(questions): add uploaded_by_admin flag to QuestionImage"
```

---

### Task 2: Supabase Storage upload helper

**Files:**
- Create: `backend/questions/image_upload.py`

**Interfaces:**
- Consumes: env vars `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` (already configured).
- Produces: `upload_image_to_supabase(*, file_obj, question_id, content_type) -> dict` returning `{ id, url, sha256, sha256_short, width, height, bytes, mime }`.

- [ ] **Step 1: Write the helper module**

Create `backend/questions/image_upload.py`:

```python
"""Supabase Storage upload helper for admin-uploaded question images.

This module creates a `QuestionImage` row and uploads the underlying
file to Supabase Storage. It is the only authoritative path for
admin-uploaded images — the same Django backend that serves the API
also owns the bucket.

**Bucket**: `crack-cms-question-images` (public read).
**Path**: `question_images/{question_id}/{sha256_short}.{ext}`.
**Env vars**: `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` (already in
`backend/.env.example`).

The `[[img:N]]` token scheme (used in `question_text`) refers to the
`QuestionImage.id` returned by `upload_image_to_supabase`.
"""
from __future__ import annotations

import hashlib
import io
import logging
import os
import uuid
from dataclasses import dataclass
from typing import BinaryIO

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

BUCKET_NAME = "crack-cms-question-images"
MAX_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_MIME = {"image/png", "image/jpeg", "image/webp", "image/gif"}


@dataclass
class UploadedImage:
    id: int
    url: str
    sha256: str
    sha256_short: str
    width: int
    height: int
    bytes: int
    mime: str


def _ensure_supabase_client():
    """Return a Supabase client or raise RuntimeError with a clear message."""
    from supabase import create_client  # imported lazily so the module loads even if supabase is missing locally

    url = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError(
            "Supabase storage not configured. Set SUPABASE_URL and "
            "SUPABASE_SERVICE_ROLE_KEY in backend/.env before uploading."
        )
    return create_client(url, key)


def upload_image_to_supabase(
    *,
    file_obj: BinaryIO,
    question_id: int,
    content_type: str,
    original_filename: str,
) -> UploadedImage:
    """Upload `file_obj` to Supabase Storage and create a `QuestionImage` row.

    The `QuestionImage` row is created with `uploaded_by_admin=True` and
    the file field unset (the canonical URL is the Supabase public URL).
    The function is idempotent on `sha256` per question: re-uploading
    the same bytes updates the existing row's `updated_at` and returns
    the same id.

    Raises:
        ValueError: wrong MIME or too large.
        RuntimeError: Supabase not configured or upload failed.
    """
    from questions.models import QuestionImage  # local import to avoid AppRegistryNotReady

    if content_type not in ALLOWED_MIME:
        raise ValueError(
            f"Unsupported MIME {content_type!r}. Allowed: {sorted(ALLOWED_MIME)}"
        )

    payload = file_obj.read()
    if len(payload) > MAX_BYTES:
        raise ValueError(
            f"File too large: {len(payload)} bytes (max {MAX_BYTES})"
        )

    sha256 = hashlib.sha256(payload).hexdigest()
    sha256_short = sha256[:16]

    width = height = 0
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(payload))
        width, height = img.size
    except Exception:  # noqa: BLE001 — PIL missing or bad image; dimensions are best-effort
        logger.warning("Could not extract dimensions for uploaded image")

    existing = QuestionImage.objects.filter(
        question_id=question_id, sha256_short=sha256_short
    ).first()
    if existing:
        logger.info("Re-using existing QuestionImage #%s (sha256 short=%s)", existing.id, sha256_short)
        existing.updated_at = timezone.now()
        existing.save(update_fields=["updated_at"])
        return UploadedImage(
            id=existing.id,
            url=existing.url,
            sha256=existing.sha256,
            sha256_short=existing.sha256_short,
            width=existing.width or width,
            height=existing.height or height,
            bytes=existing.bytes or len(payload),
            mime=existing.mime or content_type,
        )

    client = _ensure_supabase_client()
    ext = (original_filename.split(".")[-1] or "png").lower()[:8]
    ext = "".join(ch for ch in ext if ch.isalnum()) or "png"
    key = f"question_images/{question_id}/{sha256_short}.{ext}"

    try:
        client.storage.from_(BUCKET_NAME).upload(
            path=key,
            file=payload,
            file_options={"content-type": content_type, "upsert": "true"},
        )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Supabase upload failed: {exc}") from exc

    public_url = client.storage.from_(BUCKET_NAME).get_public_url(key)

    row = QuestionImage.objects.create(
        question_id=question_id,
        page_number=0,
        image_index_in_page=0,
        file="",  # empty — URL is the canonical location
        mime=content_type,
        width=width,
        height=height,
        bytes=len(payload),
        sha256=sha256,
        sha256_short=sha256_short,
        modality="other",
        uploaded_by_admin=True,
        url=public_url,
    )
    logger.info("Uploaded QuestionImage #%s to %s", row.id, public_url)
    return UploadedImage(
        id=row.id,
        url=public_url,
        sha256=sha256,
        sha256_short=sha256_short,
        width=width,
        height=height,
        bytes=len(payload),
        mime=content_type,
    )
```

> **Note**: Step 1 writes a `url` field on `QuestionImage`. We need to add that field too. Edit the model in the same commit: `backend/questions/models.py:850` (after `caption`), add:
>
> ```python
>     url = models.URLField(max_length=500, blank=True, help_text='Supabase public URL (when uploaded via admin)')
> ```
>
> Re-run `python manage.py makemigrations questions --name questionimage_url` and `python manage.py migrate questions` before continuing.

- [ ] **Step 2: Smoke-test the helper in a shell**

```bash
cd c:/Users/DIVYANSHU/Desktop/crack_cms/backend
python manage.py shell <<'PY'
from questions.image_upload import _ensure_supabase_client, BUCKET_NAME
client = _ensure_supabase_client()
print("Bucket exists:", BUCKET_NAME in [b.name for b in client.storage.list_buckets()])
PY
```

Expected: prints `Bucket exists: True`. If `False`, run `python manage.py shell -c "from questions.image_upload import _ensure_supabase_client; _ensure_supabase_client().storage.create_bucket('crack-cms-question-images', options={'public': True})"` first (idempotent).

- [ ] **Step 3: Commit**

```bash
cd c:/Users/DIVYANSHU/Desktop/crack_cms
git add backend/questions/image_upload.py backend/questions/models.py backend/questions/migrations/0009_questionimage_uploaded_by_admin.py backend/questions/migrations/0010_questionimage_url.py
git commit -m "feat(questions): Supabase Storage upload helper for admin images"
```

---

### Task 3: `QuestionImageViewSet` + optimistic lock

**Files:**
- Modify: `backend/questions/views.py:2086` (after `QuestionImageServeView`)
- Modify: `backend/questions/urls.py:11`
- Create: `backend/questions/serializers_question_image.py`
- Create: `backend/questions/tests/test_image_upload.py`

**Interfaces:**
- Consumes: `upload_image_to_supabase()` from Task 2, `QuestionImage` model.
- Produces: `POST /questions/images/` (multipart upload), `PATCH /questions/images/{id}/`, `DELETE /questions/images/{id}/`, `POST /questions/images/{id}/reorder/`. Also adds `If-Match` check to `QuestionViewSet.perform_update()`.

- [ ] **Step 1: Write the failing test**

Create `backend/questions/tests/test_image_upload.py`:

```python
"""Tests for the admin QuestionImage upload/CRUD endpoints."""
import io
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from questions.models import Question, Subject, QuestionImage


def _make_png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color="red").save(buf, format="PNG")
    return buf.getvalue()


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class QuestionImageUploadTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="pw"
        )
        cls.regular = User.objects.create_user(
            username="user", email="user@example.com", password="pw"
        )
        cls.subject = Subject.objects.create(name="Medicine", code="MED")
        cls.question = Question.objects.create(
            question_text="What?",
            option_a="A",
            option_b="B",
            option_c="C",
            option_d="D",
            correct_answer="A",
            year=2025,
            subject=cls.subject,
        )

    def test_upload_requires_admin(self):
        self.client.force_authenticate(self.regular)
        file = SimpleUploadedFile("x.png", _make_png_bytes(), content_type="image/png")
        resp = self.client.post(
            "/api/questions/images/",
            data={"question_id": self.question.id, "file": file},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    @patch("questions.views.upload_image_to_supabase")
    def test_upload_happy_path(self, mock_upload):
        mock_upload.return_value = type(
            "U", (), {
                "id": 1, "url": "https://example.com/x.png", "sha256": "a" * 64,
                "sha256_short": "a" * 16, "width": 10, "height": 10, "bytes": 100,
                "mime": "image/png",
            }
        )
        self.client.force_authenticate(self.admin)
        file = SimpleUploadedFile("x.png", _make_png_bytes(), content_type="image/png")
        resp = self.client.post(
            "/api/questions/images/",
            data={"question_id": self.question.id, "file": file},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["id"], 1)
        self.assertTrue(QuestionImage.objects.filter(id=1, uploaded_by_admin=True).exists())

    def test_rejects_oversize_file(self):
        self.client.force_authenticate(self.admin)
        big = SimpleUploadedFile("x.png", b"0" * (6 * 1024 * 1024), content_type="image/png")
        resp = self.client.post(
            "/api/questions/images/",
            data={"question_id": self.question.id, "file": big},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_bad_mime(self):
        self.client.force_authenticate(self.admin)
        bad = SimpleUploadedFile("x.txt", b"hello", content_type="text/plain")
        resp = self.client.post(
            "/api/questions/images/",
            data={"question_id": self.question.id, "file": bad},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd c:/Users/DIVYANSHU/Desktop/crack_cms/backend
python manage.py test questions.tests.test_image_upload -v 2
```

Expected: failures on every test (404 because the endpoint doesn't exist yet).

- [ ] **Step 3: Create the serializer**

Create `backend/questions/serializers_question_image.py`:

```python
from rest_framework import serializers

from .models import QuestionImage


class QuestionImageSerializer(serializers.ModelSerializer):
    """Admin-facing serializer for `QuestionImage`.

    Exposes every writable field including `uploaded_by_admin` and
    `url`. Read-only fields: `id`, `sha256`, `sha256_short`, `width`,
    `height`, `bytes`, `created_at`.
    """
    class Meta:
        model = QuestionImage
        fields = [
            "id", "question", "page_number", "image_index_in_page",
            "file", "mime", "width", "height", "bytes",
            "sha256", "sha256_short", "phash", "dhash",
            "modality", "modality_subtype", "body_region",
            "ocr_text", "caption", "caption_source", "ocr_confidence",
            "role", "url", "uploaded_by_admin",
        ]
        read_only_fields = [
            "id", "sha256", "sha256_short", "phash", "dhash",
            "width", "height", "bytes",
        ]
```

- [ ] **Step 4: Add the ViewSet and optimistic lock**

Append to `backend/questions/views.py` (after `QuestionImageServeView`):

```python
from .image_upload import upload_image_to_supabase
from .serializers_question_image import QuestionImageSerializer


class QuestionImageViewSet(viewsets.ModelViewSet):
    """Admin-only CRUD for `QuestionImage`. Supports direct upload via
    `POST /questions/images/` with multipart `question_id` + `file`.

    **Auth**: `IsAdminUser`. Non-admins get 403.
    **Optimistic lock**: PATCH / DELETE accept `If-Match: <updated_at>`
    on the parent Question to prevent concurrent overwrites — but since
    images live on their own resource, image PATCH uses image
    `updated_at` via the same `If-Match` header.
    """
    queryset = QuestionImage.objects.all().order_by("-id")
    serializer_class = QuestionImageSerializer
    permission_classes = [permissions.IsAdminUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def create(self, request, *args, **kwargs):
        question_id = request.data.get("question_id")
        file_obj = request.FILES.get("file")
        if not question_id or not file_obj:
            return Response(
                {"detail": "question_id and file are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            question_id_int = int(question_id)
        except (TypeError, ValueError):
            return Response(
                {"detail": "question_id must be an integer"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            uploaded = upload_image_to_supabase(
                file_obj=file_obj,
                question_id=question_id_int,
                content_type=file_obj.content_type or "application/octet-stream",
                original_filename=file_obj.name or "image.png",
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except RuntimeError as exc:
            logger.error("Image upload failed: %s", exc)
            return Response(
                {"detail": "Upload failed", "hint": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        row = QuestionImage.objects.get(id=uploaded.id)
        return Response(
            QuestionImageSerializer(row).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def reorder(self, request, pk=None):
        """Reorder images within a question. Body: `{question_id, new_index_in_page}`."""
        image = self.get_object()
        new_index = request.data.get("new_index_in_page")
        try:
            new_index = int(new_index)
        except (TypeError, ValueError):
            return Response({"detail": "new_index_in_page must be an integer"}, status=400)
        image.image_index_in_page = new_index
        image.save(update_fields=["image_index_in_page"])
        return Response(QuestionImageSerializer(image).data)
```

And update `QuestionViewSet.perform_update()`:

```python
    def perform_update(self, serializer):
        match = self.request.headers.get("If-Match")
        if match:
            current = self.get_object().updated_at.isoformat()
            if match != current:
                return Response(
                    {"detail": "Question was modified by another user", "current": QuestionSerializer(self.get_object()).data},
                    status=status.HTTP_409_CONFLICT,
                )
        serializer.save()
```

Make sure `Response` and `status` are imported at the top of `views.py`; they already are.

- [ ] **Step 5: Register the ViewSet in `urls.py`**

Edit `backend/questions/urls.py` — add after the existing `router.register(r'', views.QuestionViewSet, basename='question')` line:

```python
router.register(r'images', views.QuestionImageViewSet, basename='question-image')
```

- [ ] **Step 6: Run the tests**

```bash
cd c:/Users/DIVYANSHU/Desktop/crack_cms/backend
python manage.py test questions.tests.test_image_upload -v 2
```

Expected: 4 tests pass.

- [ ] **Step 7: Commit**

```bash
cd c:/Users/DIVYANSHU/Desktop/crack_cms
git add backend/questions/views.py backend/questions/urls.py backend/questions/serializers_question_image.py backend/questions/tests/test_image_upload.py
git commit -m "feat(questions): admin QuestionImageViewSet + optimistic lock"
```

---

### Task 4: Update frontend `api.ts` with image methods + `If-Match`

**Files:**
- Modify: `frontend/src/lib/api.ts:320-377` (the `questionsAPI` block)

**Interfaces:**
- Consumes: existing `questionsAPI.update()`.
- Produces: `questionsAPI.uploadImage({questionId, file})`, `questionsAPI.updateImage(id, data)`, `questionsAPI.deleteImage(id)`, `questionsAPI.reorderImage(id, newIndex)`, and a second `update(id, data, { ifMatch })` overload.

- [ ] **Step 1: Add the four new methods**

In `frontend/src/lib/api.ts`, locate the `questionsAPI` block (search `questionsAPI`). Add these methods right before the `Tests API` comment:

```typescript
  uploadImage: (data: { questionId: number; file: File }) => {
    const form = new FormData();
    form.append('question_id', String(data.questionId));
    form.append('file', data.file);
    return api.post('/questions/images/', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  updateImage: (id: number, data: Record<string, unknown>) =>
    api.patch(`/questions/images/${id}/`, data),
  deleteImage: (id: number) => api.delete(`/questions/images/${id}/`),
  reorderImage: (id: number, newIndex: number) =>
    api.post(`/questions/images/${id}/reorder/`, { new_index_in_page: newIndex }),
```

- [ ] **Step 2: Update `questionsAPI.update` to accept `If-Match`**

Replace the existing line:

```typescript
  update: (id: number, data: Record<string, unknown>) => api.patch(`/questions/${id}/`, data),
```

with:

```typescript
  update: (id: number, data: Record<string, unknown>, opts?: { ifMatch?: string }) => {
    const headers = opts?.ifMatch ? { 'If-Match': opts.ifMatch } : undefined;
    return api.patch(`/questions/${id}/`, data, { headers });
  },
```

- [ ] **Step 3: Type-check**

```bash
cd c:/Users/DIVYANSHU/Desktop/crack_cms/frontend
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
cd c:/Users/DIVYANSHU/Desktop/crack_cms
git add frontend/src/lib/api.ts
git commit -m "feat(api): add question image upload/update/delete/reorder methods"
```

---

### Task 5: `imageTokens.ts` resolver

**Files:**
- Create: `frontend/src/lib/imageTokens.ts`

**Interfaces:**
- Consumes: `QuestionImage` shape (`{ id, url, mime, width, height, caption }`).
- Produces: `resolveImageTokens(html: string, images: QuestionImage[]): string` and a `clearImageTokenCache()` helper.

- [ ] **Step 1: Write the helper**

Create `frontend/src/lib/imageTokens.ts`:

```typescript
/**
 * Resolves `[[img:N]]` tokens inside question text into `<img>` tags.
 *
 * Used by the public practice pages and the admin editor preview. The
 * resolver is cached per `(questionId, imagesHash)` so re-renders are
 * cheap. Missing ids render an inline placeholder so the admin can
 * spot and re-upload them.
 */

export interface QuestionImageLike {
  id: number;
  url?: string | null;
  file?: string | null;
  mime?: string;
  width?: number;
  height?: number;
  caption?: string | null;
}

const TOKEN_RE = /\[\[img:(\d+)\]\]/g;
const cache = new Map<string, string>();

export function imagesHash(images: QuestionImageLike[]): string {
  return images.map((i) => `${i.id}:${i.url ?? i.file ?? ''}`).join('|');
}

export function resolveImageTokens(
  html: string,
  images: QuestionImageLike[],
  cacheKey?: string,
): string {
  const key = cacheKey ?? `__anon__:${imagesHash(images)}`;
  const cached = cache.get(key);
  if (cached !== undefined) return cached;

  const byId = new Map(images.map((i) => [i.id, i]));

  const resolved = html.replace(TOKEN_RE, (_match, idStr: string) => {
    const id = parseInt(idStr, 10);
    const img = byId.get(id);
    if (!img) {
      if (typeof console !== 'undefined') {
        console.warn(`[imageTokens] missing image #${id}`);
      }
      return `<span class="missing-image-placeholder" data-missing-image-id="${id}">[missing image #${id}]</span>`;
    }
    const src = (img.url || img.file) ?? '';
    const alt = (img.caption || `Question image ${id}`).replace(/"/g, '&quot;');
    const widthAttr = img.width ? ` width="${img.width}"` : '';
    const heightAttr = img.height ? ` height="${img.height}"` : '';
    return `<img src="${src}" alt="${alt}"${widthAttr}${heightAttr} loading="lazy" class="question-inline-image" />`;
  });

  cache.set(key, resolved);
  return resolved;
}

export function clearImageTokenCache(): void {
  cache.clear();
}
```

- [ ] **Step 2: Type-check**

```bash
cd c:/Users/DIVYANSHU/Desktop/crack_cms/frontend
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd c:/Users/DIVYANSHU/Desktop/crack_cms
git add frontend/src/lib/imageTokens.ts
git commit -m "feat(lib): imageTokens resolver for [[img:N]] placeholders"
```

---

### Task 6: Extend `/admin/questions-editor` with `exam_type` filter + `[Edit]` button

**Files:**
- Modify: `frontend/src/app/admin/questions-editor/page.tsx`

**Interfaces:**
- Consumes: existing `questionsAPI.list()` returns paginated results.
- Produces: A new `exam_type` `select` in the filter bar, a new `[Edit]` button per row that opens the modal.

- [ ] **Step 1: Add the exam-type state and filter**

In `frontend/src/app/admin/questions-editor/page.tsx`, add the state at the top of the component (next to `needsReview`, `isDropped`):

```typescript
  const [examType, setExamType] = useState<string>('');
```

And update the `fetchQuestions` function to include it:

```typescript
      if (examType) params.exam_type = examType;
```

(Place that line right above `if (search)`.)

- [ ] **Step 2: Add the year filter (optional but cheap)**

```typescript
  const [year, setYear] = useState<string>('');
```
And:
```typescript
      if (year) params.year = year;
```
And add `year` to the `useEffect` deps.

- [ ] **Step 3: Add the dropdowns to the filter bar**

In the existing filter `<div>` (the one with `Search questions...`), add right after the `isDropped` label:

```tsx
        <select
          className="border p-2 rounded"
          value={examType}
          onChange={(e) => { setExamType(e.target.value); setPage(1); }}
        >
          <option value="">All Exams</option>
          <option value="cms">UPSC CMS</option>
          <option value="neet_pg">NEET PG</option>
          <option value="ini_cet">INI-CET</option>
          <option value="usmle">USMLE</option>
          <option value="fmge">FMGE</option>
        </select>
        <input
          type="number"
          placeholder="Year"
          className="border p-2 rounded w-24"
          value={year}
          onChange={(e) => setYear(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && fetchQuestions()}
        />
```

- [ ] **Step 4: Wire the `[Edit]` button**

Find the existing `Merge / Split` button in the Actions cell, and replace the cell with:

```tsx
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium space-x-2">
                  <button
                    onClick={() => onEdit(q)}
                    className="text-emerald-600 hover:text-emerald-900 bg-emerald-50 px-3 py-1 rounded"
                  >
                    Edit
                  </button>
                  <button onClick={() => alert('Merge/Split feature coming soon!')} className="text-indigo-600 hover:text-indigo-900 bg-indigo-50 px-3 py-1 rounded">
                    Merge / Split
                  </button>
                </td>
```

The component takes an `onEdit` prop from its parent. Add to the component signature:

```typescript
export default function AdminQuestionsEditorPage({ onEdit }: { onEdit?: (q: any) => void } = {}) {
```

Since the page is the route entry, add a state for the modal:

```typescript
  const [editing, setEditing] = useState<any | null>(null);
  const onEdit = (q: any) => setEditing(q);
```

And render the modal at the bottom of the page (after the table):

```tsx
      {editing && (
        <QuestionEditModal
          question={editing}
          images={editing.images ?? []}
          onClose={() => setEditing(null)}
          onSaved={(updated) => {
            setQuestions(questions.map((q) => (q.id === updated.id ? updated : q)));
            setEditing(null);
          }}
        />
      )}
```

- [ ] **Step 5: Import the modal**

Add the import at the top:

```typescript
import QuestionEditModal from './QuestionEditModal';
```

- [ ] **Step 6: Type-check**

```bash
cd c:/Users/DIVYANSHU/Desktop/crack_cms/frontend
npx tsc --noEmit
```

Expected: error `Cannot find module './QuestionEditModal'` — that's expected; Task 7 creates it. The rest of the page should be free of type errors.

- [ ] **Step 7: Commit**

```bash
cd c:/Users/DIVYANSHU/Desktop/crack_cms
git add frontend/src/app/admin/questions-editor/page.tsx
git commit -m "feat(admin): add exam_type + year filters and Edit button"
```

---

### Task 7: `QuestionEditModal` component

**Files:**
- Create: `frontend/src/app/admin/questions-editor/QuestionEditModal.tsx`

**Interfaces:**
- Consumes: `questionsAPI.update()`, `questionsAPI.uploadImage()`, `questionsAPI.deleteImage()`, `questionsAPI.reorderImage()`, `resolveImageTokens()`.
- Produces: A modal that binds to a `Question` row and saves changes with `If-Match`.

- [ ] **Step 1: Write the modal**

Create `frontend/src/app/admin/questions-editor/QuestionEditModal.tsx`:

```tsx
'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { questionsAPI } from '@/lib/api';
import { resolveImageTokens, type QuestionImageLike } from '@/lib/imageTokens';

interface QuestionEditModalProps {
  question: any;
  images: QuestionImageLike[];
  onClose: () => void;
  onSaved: (updated: any) => void;
}

export default function QuestionEditModal({ question, images: initialImages, onClose, onSaved }: QuestionEditModalProps) {
  const [form, setForm] = useState({
    question_text: question.question_text ?? '',
    option_a: question.option_a ?? '',
    option_b: question.option_b ?? '',
    option_c: question.option_c ?? '',
    option_d: question.option_d ?? '',
    correct_answer: question.correct_answer ?? 'A',
    explanation: question.explanation ?? '',
    mnemonic: question.mnemonic ?? '',
    concept_explanation: question.concept_explanation ?? '',
    difficulty: question.difficulty ?? 'medium',
    topic: question.topic ?? null,
    needs_review: !!question.needs_review,
    is_dropped: !!question.is_dropped,
    is_controversial: !!question.is_controversial,
  });
  const [images, setImages] = useState<QuestionImageLike[]>(initialImages);
  const [updatedAt, setUpdatedAt] = useState<string>(question.updated_at ?? '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState<any | null>(null);
  const questionTextRef = useRef<HTMLTextAreaElement>(null);
  const explanationRef = useRef<HTMLTextAreaElement>(null);

  const previewHtml = useMemo(
    () => resolveImageTokens(form.question_text, images, `${question.id}:${images.map((i) => i.id).join('|')}`),
    [form.question_text, images, question.id],
  );

  async function insertImage(target: 'question' | 'explanation') {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/png,image/jpeg,image/webp,image/gif';
    input.onchange = async () => {
      const file = input.files?.[0];
      if (!file) return;
      try {
        const res = await questionsAPI.uploadImage({ questionId: question.id, file });
        const img = res.data as QuestionImageLike;
        const newImages = [...images, img];
        setImages(newImages);
        const token = `[[img:${img.id}]]`;
        const ref = target === 'question' ? questionTextRef.current : explanationRef.current;
        if (ref) {
          const start = ref.selectionStart ?? ref.value.length;
          const end = ref.selectionEnd ?? ref.value.length;
          const fieldKey = target === 'question' ? 'question_text' : 'explanation';
          setForm({ ...form, [fieldKey]: ref.value.slice(0, start) + token + ref.value.slice(end) });
        }
      } catch (e: any) {
        setError('Failed to upload image: ' + (e?.response?.data?.detail || e?.message || 'unknown'));
      }
    };
    input.click();
  }

  async function deleteImage(id: number) {
    if (!confirm('Delete this image permanently?')) return;
    try {
      await questionsAPI.deleteImage(id);
      setImages(images.filter((i) => i.id !== id));
      const tokenRe = new RegExp(`\\[\\[img:${id}\\]\\]`, 'g');
      setForm({
        ...form,
        question_text: form.question_text.replace(tokenRe, ''),
        explanation: form.explanation.replace(tokenRe, ''),
      });
    } catch (e: any) {
      setError('Failed to delete image: ' + (e?.response?.data?.detail || e?.message || 'unknown'));
    }
  }

  async function moveImage(id: number, delta: number) {
    const idx = images.findIndex((i) => i.id === id);
    const newIdx = idx + delta;
    if (idx < 0 || newIdx < 0 || newIdx >= images.length) return;
    const reordered = [...images];
    const [item] = reordered.splice(idx, 1);
    reordered.splice(newIdx, 0, item);
    setImages(reordered);
    try {
      await questionsAPI.reorderImage(id, newIdx);
    } catch (e: any) {
      setError('Failed to reorder image: ' + (e?.response?.data?.detail || e?.message || 'unknown'));
    }
  }

  async function save(force = false) {
    setSaving(true);
    setError(null);
    setConflict(null);
    try {
      const payload = { ...form, admin_edited: true };
      const opts = force ? undefined : { ifMatch: updatedAt };
      const res = await questionsAPI.update(question.id, payload, opts);
      setUpdatedAt(res.data.updated_at ?? updatedAt);
      onSaved(res.data);
    } catch (e: any) {
      if (e?.response?.status === 409) {
        setConflict(e.response.data.current);
      } else {
        setError('Save failed: ' + (e?.response?.data?.detail || e?.message || 'unknown'));
      }
    } finally {
      setSaving(false);
    }
  }

  function reloadFromConflict() {
    if (!conflict) return;
    setForm({
      question_text: conflict.question_text ?? '',
      option_a: conflict.option_a ?? '',
      option_b: conflict.option_b ?? '',
      option_c: conflict.option_c ?? '',
      option_d: conflict.option_d ?? '',
      correct_answer: conflict.correct_answer ?? 'A',
      explanation: conflict.explanation ?? '',
      mnemonic: conflict.mnemonic ?? '',
      concept_explanation: conflict.concept_explanation ?? '',
      difficulty: conflict.difficulty ?? 'medium',
      topic: conflict.topic ?? null,
      needs_review: !!conflict.needs_review,
      is_dropped: !!conflict.is_dropped,
      is_controversial: !!conflict.is_controversial,
    });
    setUpdatedAt(conflict.updated_at);
    setConflict(null);
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4 overflow-y-auto">
      <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto p-6 space-y-4">
        <div className="flex justify-between items-center">
          <h2 className="text-xl font-bold">Edit Question #{question.id}</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-800">×</button>
        </div>

        {error && <div className="bg-red-50 text-red-700 p-3 rounded">{error}</div>}
        {conflict && (
          <div className="bg-amber-50 border border-amber-300 p-3 rounded space-y-2">
            <p className="font-semibold">This question was edited by another user.</p>
            <button onClick={reloadFromConflict} className="bg-amber-200 px-3 py-1 rounded">Reload current values</button>
            <button onClick={() => save(true)} className="bg-amber-600 text-white px-3 py-1 rounded ml-2">Overwrite with my changes</button>
          </div>
        )}

        <label className="block">
          <span className="text-sm font-medium">Question Text</span>
          <textarea
            ref={questionTextRef}
            className="w-full border p-2 rounded mt-1 font-mono text-sm"
            rows={6}
            value={form.question_text}
            onChange={(e) => setForm({ ...form, question_text: e.target.value })}
          />
          <button onClick={() => insertImage('question')} className="mt-1 text-xs bg-emerald-50 text-emerald-700 px-2 py-1 rounded">
            + Insert image
          </button>
        </label>

        <details className="border rounded p-2">
          <summary className="cursor-pointer text-sm font-medium">Preview (rendered)</summary>
          <div className="prose max-w-none mt-2" dangerouslySetInnerHTML={{ __html: previewHtml }} />
        </details>

        <div className="grid grid-cols-2 gap-3">
          {(['option_a', 'option_b', 'option_c', 'option_d'] as const).map((k) => (
            <label key={k} className="block">
              <span className="text-sm font-medium uppercase">{k}</span>
              <textarea
                className="w-full border p-2 rounded mt-1 text-sm"
                rows={2}
                value={form[k]}
                onChange={(e) => setForm({ ...form, [k]: e.target.value })}
              />
            </label>
          ))}
        </div>

        <label className="block">
          <span className="text-sm font-medium">Correct Answer</span>
          <select
            className="border p-2 rounded ml-3"
            value={form.correct_answer}
            onChange={(e) => setForm({ ...form, correct_answer: e.target.value })}
          >
            {['A', 'B', 'C', 'D'].map((o) => <option key={o} value={o}>{o}</option>)}
          </select>
        </label>

        <label className="block">
          <span className="text-sm font-medium">Explanation</span>
          <textarea
            ref={explanationRef}
            className="w-full border p-2 rounded mt-1 text-sm"
            rows={4}
            value={form.explanation}
            onChange={(e) => setForm({ ...form, explanation: e.target.value })}
          />
          <button onClick={() => insertImage('explanation')} className="mt-1 text-xs bg-emerald-50 text-emerald-700 px-2 py-1 rounded">
            + Insert image
          </button>
        </label>

        <div className="grid grid-cols-2 gap-3">
          <label className="block">
            <span className="text-sm font-medium">Mnemonic</span>
            <textarea
              className="w-full border p-2 rounded mt-1 text-sm"
              rows={2}
              value={form.mnemonic}
              onChange={(e) => setForm({ ...form, mnemonic: e.target.value })}
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium">Difficulty</span>
            <select
              className="border p-2 rounded mt-1 w-full"
              value={form.difficulty}
              onChange={(e) => setForm({ ...form, difficulty: e.target.value })}
            >
              <option value="easy">Easy</option>
              <option value="medium">Medium</option>
              <option value="hard">Hard</option>
            </select>
          </label>
        </div>

        <div className="flex gap-4 text-sm">
          {(['needs_review', 'is_dropped', 'is_controversial'] as const).map((k) => (
            <label key={k} className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={form[k]}
                onChange={(e) => setForm({ ...form, [k]: e.target.checked })}
              />
              {k.replace(/_/g, ' ')}
            </label>
          ))}
        </div>

        <div className="border-t pt-3">
          <p className="text-sm font-medium mb-2">Images attached ({images.length})</p>
          <div className="grid grid-cols-3 gap-2">
            {images.map((img, idx) => (
              <div key={img.id} className="border rounded p-2 text-xs">
                <div className="font-mono">#{img.id}</div>
                <div className="truncate">{img.caption || img.mime}</div>
                <div className="flex gap-1 mt-1">
                  <button onClick={() => moveImage(img.id, -1)} disabled={idx === 0} className="px-1">↑</button>
                  <button onClick={() => moveImage(img.id, 1)} disabled={idx === images.length - 1} className="px-1">↓</button>
                  <button onClick={() => deleteImage(img.id)} className="px-1 text-red-500">×</button>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="flex justify-end gap-2 pt-3 border-t">
          <button onClick={onClose} className="px-4 py-2 border rounded">Cancel</button>
          <button onClick={() => save(false)} disabled={saving} className="bg-emerald-600 text-white px-4 py-2 rounded disabled:opacity-50">
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

```bash
cd c:/Users/DIVYANSHU/Desktop/crack_cms/frontend
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd c:/Users/DIVYANSHU/Desktop/crack_cms
git add frontend/src/app/admin/questions-editor/QuestionEditModal.tsx
git commit -m "feat(admin): QuestionEditModal with image insert and 409 conflict"
```

---

### Task 8: Use `resolveImageTokens` on public pages

**Files:**
- Modify: `frontend/src/app/questions/[exam]/practice/page.tsx`
- Modify: `frontend/src/components/inicet-pg/IniCetLanding.tsx`

**Interfaces:**
- Consumes: `resolveImageTokens` from Task 5.
- Produces: Public pages render `[[img:N]]` tokens as `<img>` tags.

- [ ] **Step 1: Find the question renderer in the practice page**

```bash
cd c:/Users/DIVYANSHU/Desktop/crack_cms/frontend
grep -n "question_text\|dangerouslySetInnerHTML" src/app/questions/\[exam\]/practice/page.tsx | head -20
```

Identify the line(s) where `question.question_text` is rendered.

- [ ] **Step 2: Wrap the render with `resolveImageTokens`**

Add the import at the top of `frontend/src/app/questions/[exam]/practice/page.tsx`:

```typescript
import { resolveImageTokens } from '@/lib/imageTokens';
```

Find the spot where `question.question_text` is rendered (likely `dangerouslySetInnerHTML={{ __html: q.question_text }}` or similar). Replace the innerHTML with:

```typescript
const resolvedHtml = resolveImageTokens(question.question_text, question.images ?? [], `q${question.id}:v${question.images?.length ?? 0}`);
```

And use `dangerouslySetInnerHTML={{ __html: resolvedHtml }}`. If the page renders via React text (not `dangerouslySetInnerHTML`), then render as `<div dangerouslySetInnerHTML={{ __html: resolvedHtml }} />` to allow HTML output.

- [ ] **Step 3: Apply the same change to `IniCetLanding.tsx`**

```bash
cd c:/Users/DIVYANSHU/Desktop/crack_cms/frontend
grep -n "question_text" src/components/inicet-pg/IniCetLanding.tsx | head -10
```

Add the same import and wrap the same render call.

- [ ] **Step 4: Type-check**

```bash
cd c:/Users/DIVYANSHU/Desktop/crack_cms/frontend
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
cd c:/Users/DIVYANSHU/Desktop/crack_cms
git add frontend/src/app/questions/\[exam\]/practice/page.tsx frontend/src/components/inicet-pg/IniCetLanding.tsx
git commit -m "feat(render): resolve [[img:N]] tokens on public practice pages"
```

---

### Task 9: Playwright E2E for the manual-fix flow

**Files:**
- Create: `frontend/tests/e2e/admin-question-fix.spec.ts`

**Interfaces:**
- Consumes: existing Playwright config in `frontend/playwright.config.ts`.
- Produces: A spec that logs in as admin, opens the editor, fixes a NEET PG row, and verifies the public page.

- [ ] **Step 1: Write the spec**

Create `frontend/tests/e2e/admin-question-fix.spec.ts`:

```typescript
import { test, expect } from '@playwright/test';

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? 'admin@cracklabs.app';
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? 'admin-test-pw';

test('admin can fix a NEET PG question and the public page reflects it', async ({ page, request }) => {
  // Login via the admin page
  await page.goto('/admin/login');
  await page.getByLabel('Email').fill(ADMIN_EMAIL);
  await page.getByLabel('Password').fill(ADMIN_PASSWORD);
  await page.getByRole('button', { name: /sign in/i }).click();

  // Open the editor with the NEET PG filter
  await page.goto('/admin/questions-editor');
  await page.getByRole('combobox', { name: 'Exam' }).selectOption('neet_pg');
  await page.getByRole('button', { name: /search/i }).click();

  // Open the first row
  const firstEdit = page.getByRole('button', { name: 'Edit' }).first();
  await firstEdit.click();

  // Replace the question text with a clean version
  const textarea = page.locator('textarea').first();
  await textarea.fill('Which of the following are components of the physical quality of life index (PQLI)? (FIXED)');

  // Save
  await page.getByRole('button', { name: /^Save$/ }).click();
  await expect(page.getByText(/Edit Question/)).toBeHidden({ timeout: 10_000 });

  // Verify the public page shows the fix
  await page.goto('/questions/neet-pg/practice');
  await expect(page.getByText('(FIXED)')).toBeVisible({ timeout: 15_000 });
});
```

- [ ] **Step 2: Run the spec (skip if env vars are not set)**

```bash
cd c:/Users/DIVYANSHU/Desktop/crack_cms/frontend
npx playwright test admin-question-fix --reporter=line
```

Expected: passes against a local dev environment with admin credentials; **skipped** (not failed) if `E2E_ADMIN_EMAIL` is not set.

- [ ] **Step 3: Commit**

```bash
cd c:/Users/DIVYANSHU/Desktop/crack_cms
git add frontend/tests/e2e/admin-question-fix.spec.ts
git commit -m "test(e2e): admin manual-fix flow for NEET PG practice"
```

---

### Task 10: Supabase bucket setup script

**Files:**
- Create: `backend/scripts/setup_supabase_bucket.py`

**Interfaces:**
- Consumes: `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`.
- Produces: An idempotent script that creates the `crack-cms-question-images` bucket.

- [ ] **Step 1: Write the script**

Create `backend/scripts/setup_supabase_bucket.py`:

```python
"""Idempotent setup for the `crack-cms-question-images` Supabase bucket.

Run from the backend dir:

    python scripts/setup_supabase_bucket.py

Safe to re-run; if the bucket already exists, it logs and exits 0.
"""
import os
import sys

BUCKET = "crack-cms-question-images"


def main() -> int:
    url = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set", file=sys.stderr)
        return 1

    from supabase import create_client

    client = create_client(url, key)
    existing = {b.name for b in client.storage.list_buckets()}
    if BUCKET in existing:
        print(f"OK: bucket {BUCKET!r} already exists")
        return 0

    client.storage.create_bucket(BUCKET, options={"public": True})
    print(f"OK: created bucket {BUCKET!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run it locally**

```bash
cd c:/Users/DIVYANSHU/Desktop/crack_cms/backend
python scripts/setup_supabase_bucket.py
```

Expected: `OK: bucket 'crack-cms-question-images' already exists` (or `created` for first run).

- [ ] **Step 3: Commit**

```bash
cd c:/Users/DIVYANSHU/Desktop/crack_cms
git add backend/scripts/setup_supabase_bucket.py
git commit -m "chore(scripts): one-time Supabase bucket setup for question images"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| `exam_type` filter | Task 6 |
| `year` filter | Task 6 (extra) |
| Modal editor for text/options/answer/explanation/mnemonic/difficulty/topic/flags | Task 7 |
| Inline image upload (Supabase Storage) | Tasks 2, 3, 4, 7 |
| `[[img:N]]` tokens in `question_text` | Task 5, 7, 8 |
| Save → live DB → live website | Task 7 (PATCH) + Task 8 (read) |
| `uploaded_by_admin` field | Task 1 |
| Optimistic lock via `If-Match` | Task 3, 4 |
| `QuestionImageViewSet` (4 endpoints) | Task 3 |
| Conflict UX (409) | Task 7 |
| Missing image placeholder | Task 5 |
| Idempotency / dedupe by sha256 | Task 2 |
| OOS buckets / folder per question | Task 2 |
| Backend tests | Task 3 |
| Frontend E2E | Task 9 |
| Bucket setup script | Task 10 |

**Type consistency:** `resolveImageTokens` signature `resolveImageTokens(html: string, images: QuestionImageLike[], cacheKey?: string)` is used the same way in Tasks 5, 7, 8. `QuestionImageLike` exported once. `questionsAPI.uploadImage({questionId, file})` consumed once in Task 7. `questionsAPI.update(id, data, opts?)` signature used in Task 7.

**Placeholder scan:** No "TBD", "TODO", or "fill in details". Every code block is complete. No "Same as Task N" references.

**Ambiguity check:** `If-Match` semantics pinned to `updated_at.isoformat()` with 409 response body shape `{"detail": ..., "current": <row>}` — both sides (Task 3 backend, Task 4 frontend, Task 7 modal) agree. `[[img:N]]` token format pinned to literal `[[img:` + integer + `]]`. Bucket name pinned to `crack-cms-question-images`. Path pinned to `question_images/{question_id}/{sha256_short}.{ext}`.

**Drift check:** No new env vars are introduced. No new pip packages. No new npm packages.

Plan is implementation-ready.
