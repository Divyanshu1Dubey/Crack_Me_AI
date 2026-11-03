# Running CrackLabs without Supabase: Railway backend + Railway PostgreSQL (2026-11-03)

Supabase (database **and** sign-in) is gone and the DigitalOcean app no longer exists
(`crackcms-vsthc.ondigitalocean.app` does not resolve). Since 2026-11-03 `api.cracklabs.app` is served by
a Railway service running the previous `main`, pointed by the owner at the database `cracklabs` (health
and the public question list answer; sign-in still expects Supabase, so nobody can sign in). This branch (`production-recovery`) keeps the
backend on Railway and signs people in with Django itself (`AUTH_PROVIDER=django`). The frontend stays
on Vercel.

## 1. Database (done on 2026-11-03)

* Server: the project's Railway PostgreSQL 18 instance (connection details only in Railway and in
  the untracked `backend/.env`).
* **Database `cracklabs`** = a faithful restore of the last Supabase backup
  (`db_cluster-02-10-2026@08-24-39`, public schema): 103 tables, 108,625 rows, 154 foreign keys,
  501 indexes, every user keeps his original id. Supabase-only row-level-security switches were left out.
* The database **`railway`** on the same server was **not touched**. It holds another application's
  tables (posts, categories, games, jobs, a NextAuth `users`/`accounts` set …) plus a damaged copy of the
  CrackLabs tables: its 407 user rows were renumbered (none of the 127 real users kept its id) and 270
  `deleted_user` placeholders fill the gaps, so 1,445 of 1,450 question attempts, every bookmark and the
  paid subscription point at the wrong person, and 101 of 110 test attempts are missing. Do not point
  the backend at it.
* Supabase sign-in data (bcrypt password hashes, Google account ids) is imported into `cracklabs` by
  `python manage.py import_supabase_auth --source-url <local restore of the Supabase backup> --apply
  --create-missing` (dry run without `--apply`). Users keep their password; Google users sign in with
  the same Google account (matched on Google's account id, never on email alone). Passwords of
  staff/admin accounts are not imported unless an operator names the account
  (`--allow-privileged-password UID`); such accounts sign in with Google or set a new password through
  "Forgot password". A Google identity created after its Django account is only linked by an operator
  (`--include-newer-identities --only-uid UID`) after checking that it belongs to the same person. The
  import is idempotent: running it again reports every account as already linked.

## 2. Backend service on Railway

Use the existing Railway service behind `api.cracklabs.app` (or create one from the GitHub repo
`Divyanshu1Dubey/Crack_Me_AI`, branch `main` once this branch is merged) with these settings:

| Setting | Value |
|---|---|
| Root directory | `backend` |
| Config file | `backend/railway.json` (build: collectstatic; pre-deploy: `bash release.sh` = migrate + idempotent seeds, database only, because Railway mounts no volume in the pre-deploy container; start: `bash start_web.sh` = the media steps in the background (media restore, fixture image relinking) + the django-q worker + gunicorn; health check `/api/health/`) |
| Volume | mount at `/data` (5 GB is plenty) |
| Custom domain | `api.cracklabs.app` (then in Cloudflare: CNAME `api` → the `*.up.railway.app` target Railway shows; SSL mode Full) |

### Variables (Railway → service → Variables)

Required:

| Name | Value |
|---|---|
| `DATABASE_URL` | `postgresql://${{Postgres.PGUSER}}:${{Postgres.PGPASSWORD}}@${{Postgres.RAILWAY_PRIVATE_DOMAIN}}:5432/cracklabs` (private network; note the database name **cracklabs**) |
| `DJANGO_SECRET_KEY` | the existing production secret (keeps signed links valid) |
| `DEBUG` | `False` |
| `ALLOWED_HOSTS` | `api.cracklabs.app,.up.railway.app` (on Railway the settings add `healthcheck.railway.app`, the Host of Railway's health check, and `/api/health/` is exempt from the HTTPS redirect, so the plain-HTTP check gets its 200) |
| `FRONTEND_URL` | `https://www.cracklabs.app` |
| `CORS_ALLOWED_ORIGINS` / `CSRF_TRUSTED_ORIGINS` | `https://cracklabs.app,https://www.cracklabs.app` |
| `AUTH_PROVIDER` | `django` |
| `JWT_SIGNING_KEY` | a new random value (e.g. `python -c "import secrets; print(secrets.token_urlsafe(64))"`) |
| `GOOGLE_OAUTH_CLIENT_IDS` | the Google OAuth **web** client id used for "Sign in with Google". The one Supabase used is recorded as `478102887382-sjas9kfguccgj9qhkhpjcoog1h0akko0.apps.googleusercontent.com`: confirm it in Google Cloud console → APIs & Services → Credentials and add the Authorized JavaScript origins `https://cracklabs.app` and `https://www.cracklabs.app`. Google's account id (`sub`) is the same for every OAuth client, so the imported Google identities match with this client or a new one; reusing it saves setting up a new consent screen. |
| `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` / `DEFAULT_FROM_EMAIL` | the existing SMTP account (password-reset and verification mails) |
| `MEDIA_ROOT` | `/data/media` |
| `SUPABASE_STORAGE_MIRROR_DIR` | `/data/storage-mirror` (serves the 495 images whose stored URL is an old Supabase Storage URL) |
| `CORE_DATA_BACKUP_PATH` | `/data/backups/core_data.json` (a file path; its folder is created) |
| `TRUSTED_CLIENT_IP_HEADER` | `CF-Connecting-IP` (Cloudflare in front) |

Keep from the old deployment: the AI provider keys, `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` /
`RAZORPAY_WEBHOOK_SECRET`, `SENTRY_DSN` (optional). Remove every `SUPABASE_*` variable.

### Media (question images, mock-test assets, videos)

The volume starts empty. `scripts/railway/upload_media_to_db.py` stages the files in the table
`ops_media_transfer` of `cracklabs` (from the local copies: `backend/media/recall_images` (3,579 question
images + 172 page screenshots), `backend/media/mocktest_assets`, and the restored Supabase Storage bucket
`crack-cms-question-images` (the 495 admin-uploaded images)). After each start, `start_web.sh` writes
missing files onto `/data` in the background (`manage.py restore_media_transfer`, idempotent, SHA-256
checked; the deploy log shows `start_web.sh: media steps complete`). This cannot run in `release.sh`:
Railway's pre-deploy container has no volume and discards its files. Once images show in production,
free the space: `python manage.py restore_media_transfer --drop` (or `DROP TABLE ops_media_transfer;`).

Without Supabase, new admin image uploads are stored on the volume too (`questions/image_upload.py`).

Not covered yet: the 21 explanation **videos** still point at Supabase Storage URLs and the frontend plays
them directly; their files are in the storage backup (`educational_videos`, 248 MB) and need a public host
(e.g. a Cloudflare R2 bucket) plus a URL rewrite.

## 3. Frontend on Vercel

Environment variables (Production), then redeploy:

| Name | Value |
|---|---|
| `NEXT_PUBLIC_API_URL` | `https://api.cracklabs.app/api` |
| `NEXT_PUBLIC_AUTH_MODE` | `django` |
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | the same Google web client id |

Remove `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY` / `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`
(ignored in django mode; the build works without them).

* The Google button only renders when `NEXT_PUBLIC_GOOGLE_CLIENT_ID` is set; it uses Google Identity
  Services in popup mode, so the client needs the Authorized JavaScript origins listed above (add
  `http://localhost:3000` for local testing) and no redirect URI.
* The Content-Security-Policy in `frontend/vercel.json` allows `api.cracklabs.app` and
  `accounts.google.com` (Google's script, button stylesheet and popup). If `NEXT_PUBLIC_API_URL` or
  `NEXT_PUBLIC_API_FALLBACK_URL` points at another host (for example `*.up.railway.app`), add that host to
  `connect-src` or the browser blocks the calls.
* Old Supabase emails (confirmation, magic link, recovery) open `/auth/callback`, which now explains that
  the link is no longer valid and sends the visitor to `/login`.
* The Capacitor app (`mobile-app/`) cannot use the Google button: Google blocks sign-in inside embedded
  WebViews. Email + password works there; a native Google plugin is a follow-up.

## 4. Order of operations

1. Merge `production-recovery` into `main` (Vercel and the Railway service deploy `main`).
2. Railway: apply the settings and variables above (volume, domain); the deploy runs `release.sh`
   (migrations, seeds) before the new version starts, and the started container restores the media
   in the background. Check `GET /api/auth/config/` →
   `{"auth_provider": "django", ...}` before switching the frontend: a django-mode frontend in front of
   a backend still on Supabase shows "Sign-in is not available right now".
3. Cloudflare: `api.cracklabs.app` → the Railway service (already the case on 2026-11-03).
4. Vercel: set the variables, redeploy.
5. Check: `https://api.cracklabs.app/api/health/` → 200; sign in with an existing email/password
   account and with Google; "Forgot password" → the emailed link sets a new password and the old one is
   refused; a third device of a free account lands on `/settings?deviceLimit=1`; signing out in one tab
   signs the other tabs out; open a question with an image.
6. Rotate the Railway database password (Railway → Postgres → Variables) and update `DATABASE_URL`
   wherever it is used outside the private network.
