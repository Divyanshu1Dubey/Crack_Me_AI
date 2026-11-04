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
  `python manage.py import_supabase_auth` (dry run unless `--apply`). Users keep their password; Google
  users sign in with the same Google account (matched on Google's account id, never on email alone). The
  import is idempotent: running it again reports every account as already linked. Procedure:
  1. **Published passwords file.** Some Supabase hashes are of passwords that were committed to this
     (public) repository -- the default password once in
     `backend/accounts/management/commands/bootstrap_admin.py` (removed in `f011c1d`), QA / E2E
     passwords. Write every such literal from the git history into a file OUTSIDE the repository, one per
     line exactly as typed (the commands refuse a path inside the work tree and never print it).
  2. **Dry run and review**: `import_supabase_auth --source-url <local restore of the Supabase backup>
     --create-missing --leaked-password-file <file> --report <path outside the repo>`. A hash of a
     published password is never imported (`PASSWORD_WITHHELD_LEAKED`; the account is still linked, so
     "Forgot password" and Google work), and an auth user without a Django row whose password is published
     is not created (`MISSING_LEAKED_PASSWORD`). Review the `CREATE` rows of the report (`created_at`,
     `last_sign_in_at`): some may have been deleted on purpose; skip them with `--exclude-uid UID`. Other
     accounts whose hash must not be imported: `--no-password-for EMAIL` / `--no-password-for-uid UID`.
  3. **Apply** with the same options plus `--apply`, then run it once more (everything unchanged).
  4. **Hashes imported earlier** (an earlier `--apply` without the file; the dry run reports them as
     `WITHHELD_HASH_ALREADY_IMPORTED`): `python manage.py withhold_leaked_passwords --password-file <file>`
     (dry run: counts; `-v 2`: account ids), then `--apply`. It makes every account password that verifies a
     published one unusable -- an imported hash, its Argon2 re-hash after a sign-in, or a Django password --
     and ends those accounts' sessions; the owners use "Forgot password" or Google.
     `--user-id N` without the file only clears hashes still imported unchanged (`supabase_bcrypt$`).

  Passwords of staff/admin accounts are **never** imported (there is no override): an admin signs in with
  Google, "Forgot password" or `python manage.py changepassword <username>`. A Google identity created after
  its Django account is only linked by an operator (`--include-newer-identities --only-uid UID`) after
  checking that it belongs to the same person.

## 2. Backend service on Railway

Use the existing Railway service behind `api.cracklabs.app` (or create one from the GitHub repo
`Divyanshu1Dubey/Crack_Me_AI`, branch `main` once this branch is merged) with these settings:

| Setting | Value |
|---|---|
| Root directory | `backend` |
| Config file | **`/backend/railway.json`**: Railway → service → Settings → Config-as-code → Railway Config File, the full path from the repository root (the setting does not follow the Root Directory). The file sets build: collectstatic; pre-deploy: `bash release.sh` = migrate + idempotent seeds, database only, because Railway mounts no volume in the pre-deploy container; start: `bash start_web.sh` = migrate again (a no-op after release.sh) + the media steps in the background (media restore, fixture image relinking) + the django-q worker + gunicorn; health check `/api/health/` |
| Volume | mount at `/data` (5 GB is plenty) |
| Custom domain | `api.cracklabs.app` (then in Cloudflare: CNAME `api` → the `*.up.railway.app` target Railway shows; SSL mode Full) |

### Check that Railway uses the config file

With the Config File setting empty, Railway reads no config file: none of its settings apply (pre-deploy
`release.sh`, `start_web.sh`, the health check, the restart policy) unless the dashboard sets the same
values, and Railpack's default start command is the `web` line of `backend/Procfile`; Railway never runs
the Procfile `release` line. Until 2026-11-04 that `web` line was gunicorn alone: the 2026-11-03 deploys
needed `accounts.0028` / `0029` applied by hand, and the 2026-11-04 deploy went live without its 7
migrations, so every signed-in request and `/api/questions/` answered 500 (missing columns) while
`/api/health/` answered 200, and the blog was empty (`seed_blogs` had not run). Both start commands now run
`migrate --no-input` before gunicorn, so a deploy can no longer serve a database without its migrations,
but the seeds and the media steps still need the config file. After a deploy check:

* the top of the build log names `backend/railway.json`; the deploy log shows `release.sh complete` and
  `start_web.sh: media steps complete`;
* `python manage.py showmigrations --plan | grep "\[ \]"` (or `migrate --plan`) lists nothing.

If a deploy went out without its migrations: from a checkout of the deployed commit, with an env file whose
`DATABASE_URL` reaches the database through Railway's public TCP proxy,
`DJANGO_ENV_FILE=<file> python manage.py migrate --plan`, then `migrate`, then `seed_blogs --dry-run` and
`seed_blogs`; or set the Config File and redeploy. Every migration is its own transaction, so a failure
rolls that migration back and a second run continues.

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
| `TRUSTED_CLIENT_IP_HEADER` | `CF-Connecting-IP` (Cloudflare in front): the visitor's address for the sign-in rate limits, lockouts and the question-bank limiter. |

Client address, hardening (opt-in; set these only after the check below):

| Name | Value |
|---|---|
| `NUM_PROXIES` | The number of proxies that append to `X-Forwarded-For` in front of Django (Railway: expected `1`). There is no default: until it is set, DRF throttles keep their historical key and `check --deploy` warns `accounts.W007`. |
| `TRUSTED_CLIENT_IP_HEADER_FROM` | `cloudflare`: `CF-Connecting-IP` is then read only when the hop Railway appended is one of Cloudflare's published addresses, so a request sent to the origin directly (around Cloudflare) cannot name its own client address. Unset = `any` (the header is read from every peer, as before). Also accepts CIDRs. |
| `TRUSTED_CLIENT_IP_SECRET` / `TRUSTED_CLIENT_IP_SECRET_HEADER` | A random value that a Cloudflare Transform Rule (Rules → Transform Rules → Modify Request Header, zone `cracklabs.app`) adds as a request header (default name `X-Edge-Auth`). Then the header is only read from requests through this zone. This works whatever Railway does with `X-Forwarded-For`. |

Why opt-in: Railway does not document whether its edge appends to or replaces `X-Forwarded-For`, and
reports of extra CDN layers in its edge differ. If the right-most hop is not Cloudflare's address,
`TRUSTED_CLIENT_IP_HEADER_FROM=cloudflare` would put every visitor into one rate-limit bucket. Check first,
as an admin: `GET https://api.cracklabs.app/api/health/client-ip/` shows `remote_addr`, the raw
`X-Forwarded-For` chain and the edge headers. If the right-most `X-Forwarded-For` entry is a Cloudflare
address (`crack_cms/client_ip.py` lists the ranges), set `NUM_PROXIES=1` and
`TRUSTED_CLIENT_IP_HEADER_FROM=cloudflare`, then check again: `peer` = a Cloudflare address,
`edge_header_honoured: true`, `client_ip` = your own public address; and on the `*.up.railway.app`
hostname with forged headers (`X-Forwarded-For: 1.2.3.4`, `CF-Connecting-IP: 1.2.3.4`) `client_ip` must
still be your real address with `edge_header_honoured` false. If the right-most entry is something else,
use the Transform Rule secret instead (with `TRUSTED_CLIENT_IP_HEADER_FROM=any`).

Until one of the two is done, `check --deploy` warns `accounts.W007`: a request sent to the origin directly
(around Cloudflare) can name its own client address and get fresh sign-in rate-limit buckets; the per-email
limits still cap guessing on one account. Removing the service's public `*.up.railway.app` domain (Railway →
service → Settings → Networking) closes the obvious way around Cloudflare in the meantime, not every one.
`TRUSTED_CLIENT_IP_HEADER_FROM` set without `NUM_PROXIES` is an error (`accounts.E001`): `migrate` in the
release step refuses to run, so that deploy stops and the previous version keeps serving.

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
(ignored in django mode; the build works without them). A build with `NEXT_PUBLIC_AUTH_MODE` unset and no
Supabase keys also runs in django mode; the middleware never fails a request (it used to throw on every
page, Vercel `MIDDLEWARE_INVOCATION_FAILED`, when the Supabase keys were removed before the mode was set).

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
2. Before the backend runs `AUTH_PROVIDER=django`: the sign-in import and the published-password steps of
   section 1 (`import_supabase_auth --leaked-password-file ...`, then `withhold_leaked_passwords
   --password-file ... --apply` wherever an earlier import already wrote hashes). Admin accounts get a new
   password (`manage.py changepassword` or "Forgot password"); rotate that password wherever else it was used.
3. Railway: apply the settings and variables above (volume, domain; the client-address hardening after
   its check); the deploy runs
   `release.sh` (migrations, seeds) before the new version starts, and the started container restores the
   media in the background. Check `GET /api/auth/config/` → `{"auth_provider": "django", ...}` before
   switching the frontend (a django-mode frontend in front of a backend still on Supabase shows "Sign-in is
   not available right now"), and the client address as described under the variables.
4. Cloudflare: `api.cracklabs.app` → the Railway service (already the case on 2026-11-03).
5. Vercel: set the variables, redeploy.
6. Check: `https://api.cracklabs.app/api/health/` → 200; sign in with an existing email/password
   account and with Google; "Forgot password" → the emailed link sets a new password and the old one is
   refused; a new sign-up's emailed link asks for the password chosen at sign-up; a third device of a free
   account lands on `/settings?deviceLimit=1`; signing out in one tab signs the other tabs out; open a
   question with an image.
7. Rotate the Railway database password (Railway → Postgres → Variables) and update `DATABASE_URL`
   wherever it is used outside the private network.
