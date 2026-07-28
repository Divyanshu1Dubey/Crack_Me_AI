# Giscus Discussions Setup (one-time, ~10 minutes)

The blog post discussion thread uses Giscus — a lightweight, open-source
widget that turns [GitHub Discussions](https://github.com/features/discussions)
into a comment system. Comments are stored on GitHub (no third-party
tracker, no spam signup), and the widget is dark-mode aware.

You only need to do this once. After the GitHub repo + Discussions are
set up, every blog post route gets its own free discussion thread.

---

## Step 1 — Choose or create a GitHub repo

Any public repo you own will work. The convention we use at CrackCMS is:

```
https://github.com/Divyanshu1Dubey/CrackCMS-Blog-Discussions
```

> If you'd rather reuse the existing product repo
> (`Divyanshu1Dubey/Crack_Me_AI`), that's fine — just enable Discussions
> on it. The product repo is already public.

## Step 2 — Enable Discussions on the repo

1. Open the repo on GitHub → **Settings** → **General** → **Features**.
2. Tick **Discussions**.
3. Click **Set up discussions**.
4. GitHub will offer to create a default category — call it
   `Blog — General`. Add one more category called `Blog — Question`
   for STEM-specific follow-ups.

## Step 3 — Install the Giscus GitHub App

1. Visit [github.com/apps/giscus](https://github.com/apps/giscus) and
   install the app.
2. Grant it access to the repo you chose in Step 1.

## Step 4 — Generate your Giscus config

1. Go to [giscus.app](https://giscus.app/).
2. Fill the form:
   - **Repository**: `Divyanshu1Dubey/CrackCMS-Blog-Discussions`
     (or your repo).
   - **Discussion category**: `Blog — General`.
   - **Mapping**: choose **Discussion title contains `slug`** so each
     blog post slug becomes its own thread.
   - **Theme**: pick `light` and `dark` (Giscus auto-switches).
   - **Language**: `en`.
3. Copy the generated `data-repo`, `data-repo-id`, `data-category`,
   `data-category-id` values.

## Step 5 — Paste the values into the frontend

Open `frontend/src/components/CommentsGiscus.tsx`. Find the constant
near the top of the file:

```ts
const NEXT_PUBLIC_GISCUS_REPO = 'YOUR_GH_USER/YOUR_GH_REPO';
const NEXT_PUBLIC_GISCUS_REPO_ID = 'R_xxxxxx';
const NEXT_PUBLIC_GISCUS_CATEGORY = 'Blog — General';
const NEXT_PUBLIC_GISCUS_CATEGORY_ID = 'DIC_xxxxxx';
```

Replace the four placeholders with the values from giscus.app.

That's it. The component is already wired into every blog post page
and will start a new discussion per post slug automatically. If you
later want to embed discussions on guides or exam landing pages, just
import `<CommentsGiscus slug="…" />` and pass the page slug.

## Verification

Once the values are set:

1. `cd frontend && npm run dev`.
2. Open `/blog/upsc-cms-last-5-days-strategy`.
3. Scroll to "Join the discussion" — the Giscus iframe should appear.
4. Post a test comment via GitHub; verify it shows up on the page.

## Notes

- Giscus is free, open-source, and runs entirely client-side. No
  server changes required.
- If you'd prefer a different comments system (Cusdis, Hyvor,
  Utterances), the `<CommentsGiscus>` wrapper is intentionally
  isolated — swap its internals without touching any blog layout.
- The component is a Client Component (`'use client'`) so it does not
  affect SSG.
