# Supabase Quota Rescue Plan

Since your Supabase organization has already exceeded the 5GB Egress limit (at 25.92 GB) and your grace period ends on July 19, 2026, **Supabase will restrict your project tomorrow**. 

To stay on the **Free Plan** without losing data or experiencing downtime, we need to perform a "Project Swap" and then plug the egress leak.

## Phase 1: The "Project Swap" (Immediate Fix)

You cannot reset the quota on your current organization without upgrading to Pro. However, Supabase quotas are per **Organization**.

1. **Create a New Organization & Project**
   - Go to your Supabase Dashboard.
   - Create a **New Organization** (e.g., `CrackCMS-Prod-2`).
   - Create a **New Project** inside this new organization. (This gives you a fresh 5GB Free Plan quota).

2. **Provide Me the Credentials**
   Once the new project is ready, paste the following credentials for **both** the OLD and NEW projects in our chat:
   - **Database Connection String** (`postgresql://...`)
   - **Supabase URL**
   - **Supabase Service Role Key**

3. **I Will Perform the Migration**
   I will run a script to safely clone your database schema, data, and Auth users from the old project to the new one. No data will be lost.

4. **Swap Environment Variables**
   We will update your Django (`.env`) and Next.js (`.env.local`) files with the new project's credentials. Your app will instantly be back to normal with 0/5GB egress used.

---

## Phase 2: Plug the Egress Leak (Long-term Fix)

Your app is burning **~3.3 GB of egress per day**. This is massive for a free-tier app and means we are fetching too much data from the database. 

Once the migration is done, I will help you fix this by:
1. **Adding Caching:** We will cache massive queries (like questions or tests) in memory so Django doesn't hit Supabase for every request.
2. **Pagination Checks:** Ensure no endpoint is accidentally returning your entire `questions_fixture.json` (116,000+ lines) at once.
3. **Database Connection Optimization:** If Django is querying the database too inefficiently, we can optimize the ORM calls with `select_related` and `prefetch_related`.

---

**Next Step:** Please go to Supabase, create the new Organization and Project, and share the new connection strings here so I can start the migration!
