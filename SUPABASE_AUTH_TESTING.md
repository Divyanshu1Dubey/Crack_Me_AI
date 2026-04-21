# Supabase-Only Authentication Testing Guide

## System Status
- ✅ Backend: Supabase-only auth configured
- ✅ Frontend: Supabase session-based auth
- ✅ Admin role: Synced from Supabase metadata
- ✅ Local JWT login: Disabled (returns 410 Gone)

## Prerequisites
1. **Supabase Project**: Must be configured with `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY`
2. **Backend Running**: `python manage.py runserver` on localhost:8000
3. **Frontend Running**: `npm run dev` on localhost:3000
4. **CORS**: Backend CORS must allow frontend origin (http://localhost:3000)

## Test Scenario 1: Regular Student User

### Setup
1. In Supabase Dashboard → Authentication → Users
2. Click "Add user"
3. Email: `student@example.com`
4. Password: `TestStudent123!`
5. User metadata (JSON):
   ```json
   {
     "username": "student_001",
     "first_name": "John",
     "last_name": "Student",
     "target_exam": "UPSC CMS"
   }
   ```
6. Click "Create user"

### Test Steps
1. Open browser → http://localhost:3000/login
2. Enter email: `student@example.com`
3. Enter password: `TestStudent123!`
4. Click "Sign In"
5. **Expected Result**: 
   - ✅ Login successful
   - ✅ Redirected to `/dashboard` (student dashboard)
   - ✅ Not redirected to `/admin`

### Verification
```bash
# Backend: Check if user was created as student
python manage.py shell
>>> from django.contrib.auth import get_user_model
>>> User = get_user_model()
>>> u = User.objects.get(email='student@example.com')
>>> print(u.role, u.is_superuser, u.is_staff)
# Expected output: student False False
```

---

## Test Scenario 2: Admin User

### Setup
1. In Supabase Dashboard → Authentication → Users
2. Click "Add user"
3. Email: `admin@example.com`
4. Password: `TestAdmin123!`
5. User metadata (JSON):
   ```json
   {
     "is_admin": true,
     "username": "admin_user",
     "first_name": "Admin",
     "last_name": "User",
     "target_exam": "UPSC CMS"
   }
   ```
6. Click "Create user"

### Test Steps
1. Open browser → http://localhost:3000/login
2. Enter email: `admin@example.com`
3. Enter password: `TestAdmin123!`
4. Click "Sign In"
5. **Expected Result**:
   - ✅ Login successful
   - ✅ Redirected to `/admin` (admin dashboard)
   - ✅ Admin page stays accessible (no redirect to login)

### Verification
```bash
# Backend: Check if user was created as admin
python manage.py shell
>>> from django.contrib.auth import get_user_model
>>> User = get_user_model()
>>> u = User.objects.get(email='admin@example.com')
>>> print(u.role, u.is_superuser, u.is_staff)
# Expected output: admin True True

# Frontend: Check browser console
>>> useAuth() returns user with is_admin: true, role: 'admin'
```

---

## Test Scenario 3: Upgrade Student to Admin

### Setup
1. Create a student user first (see Test Scenario 1)
2. In Supabase Dashboard → Authentication → Users
3. Find the student user
4. Click "Edit user"
5. Update metadata:
   ```json
   {
     "is_admin": true,
     "username": "student_001",
     "first_name": "John",
     "last_name": "Student",
     "target_exam": "UPSC CMS"
   }
   ```
6. Save changes

### Test Steps
1. Go to admin dashboard (if already logged in)
2. Navigate to `/dashboard` (student area)
3. Click "Sign Out"
4. Log in again with same email
5. **Expected Result**:
   - ✅ Login successful
   - ✅ Redirected to `/admin` (not `/dashboard`)
   - ✅ Backend user updated: `role='admin'`, `is_superuser=True`

### Verification
```bash
# Backend: Check updated user
python manage.py shell
>>> from django.contrib.auth import get_user_model
>>> User = get_user_model()
>>> u = User.objects.get(email='student@example.com')
>>> print(u.role, u.is_superuser, u.is_staff)
# Expected output: admin True True (changed from student False False)
```

---

## Test Scenario 4: Admin Page Navigation

### Prerequisites
- Logged in as admin (see Test Scenario 2)

### Test Steps
Navigate through each admin tab and verify access:

1. **Overview Tab** - Dashboard summary
2. **Users Tab** - User management
3. **Feedback Tab** - Feedback queue
4. **Questions Tab** - Question bank control
5. **Tests Tab** - Test administration
6. **Textbooks Tab** - Textbook management
7. **Analytics Tab** - Analytics dashboard
8. **Moderation Tab** - Moderation queue
9. **Broadcast Tab** - Campaign management
10. **Security Tab** - Security settings
11. **Audit Tab** - Audit logs
12. **Finance Tab** - Token management
13. **AI Tab** - AI system control

### Expected Result
- ✅ All tabs load without errors
- ✅ No redirect to `/login` on page refresh
- ✅ Inline editing works (if implemented)
- ✅ Search/filter functionality works

---

## Test Scenario 5: Session Persistence

### Test Steps
1. Log in as admin (Test Scenario 2)
2. Navigate to `/admin`
3. Verify dashboard loads
4. **Close browser or refresh page**
5. Navigate to `http://localhost:3000/admin` directly
6. **Expected Result**:
   - ✅ Admin page opens directly (no login required)
   - ✅ Auth state preserved from Supabase session
   - ✅ User info displays correctly

### Verification
```bash
# Browser DevTools → Application → Cookies → supabase-auth-token
# Should contain valid Supabase session
```

---

## Test Scenario 6: Logout and Re-login

### Test Steps
1. Log in as admin (Test Scenario 2)
2. Click "Logout" button in navbar
3. **Expected Result**:
   - ✅ Logged out
   - ✅ Redirected to `/login`
   - ✅ Session cleared from Supabase
4. Try to navigate to `/admin`
5. **Expected Result**:
   - ✅ Redirected to `/login` (not accessible)
6. Log in again with same credentials
7. **Expected Result**:
   - ✅ Login successful
   - ✅ Redirected to `/admin`

---

## Test Scenario 7: Backend API Direct Call

### Prerequisites
- Admin user created (Test Scenario 2)
- Admin user already logged in once (to create local user)

### Test Steps
```bash
# Get Supabase session token (from browser console)
# Copy: useAuth().user.id (or use any logged-in user)

# Call profile endpoint with Supabase token
curl -H "Authorization: Bearer <supabase_access_token>" \
  http://localhost:8000/api/auth/profile/

# Expected output:
{
  "id": 1,
  "username": "admin_user",
  "email": "admin@example.com",
  "first_name": "Admin",
  "last_name": "User",
  "role": "admin",
  "is_admin": true,
  "target_exam": "UPSC CMS",
  "is_superuser": true,
  "is_staff": true,
  "is_active": true,
  ...
}
```

### Verification
- ✅ `role` is "admin"
- ✅ `is_admin` is true
- ✅ `is_superuser` is true
- ✅ `is_staff` is true

---

## Test Scenario 8: Disabled Local Login Endpoint

### Test Steps
```bash
# Try to call disabled local login endpoint
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin_user", "password": "TestAdmin123!"}'

# Expected response: 410 Gone
{
  "detail": "Local login is disabled. Please use Supabase authentication at /auth/login.",
  "error": "endpoint_gone"
}
```

### Verification
- ✅ HTTP status: 410 Gone
- ✅ Error message mentions Supabase
- ✅ Not authenticated (no JWT token returned)

---

## Troubleshooting

### Issue: Admin page redirects to login immediately
**Check**:
1. Is Supabase session active? (Check browser cookies)
2. Does admin user have `is_admin: true` in metadata?
3. Did user log out and log back in after metadata change?
4. Backend logs show "403 Unauthorized" on `/api/auth/profile/`?

**Solution**:
- Verify Supabase metadata is correctly set
- Check backend environment variables for Supabase URL and keys
- Ensure `SupabaseJWTAuthentication` is first in DRF auth list

### Issue: Profile endpoint returns 401 Unauthorized
**Check**:
1. Is Supabase token valid and not expired?
2. Is backend `SUPABASE_URL` and `SUPABASE_ANON_KEY` correctly configured?
3. Run backend check: `python manage.py check --deploy`

**Solution**:
- Verify Supabase environment variables
- Test Supabase token validity directly

### Issue: Admin metadata not syncing after update
**Check**:
1. Did user log out and log back in?
2. Is browser session still active (might need refresh)?
3. Check backend logs for any errors

**Solution**:
- Log out completely
- Clear all Supabase cookies
- Log in again fresh

---

## Command Reference

### Start Backend
```bash
cd backend
python manage.py migrate  # If needed
python manage.py runserver
```

### Start Frontend
```bash
cd frontend
npm run dev
```

### Run Backend Tests
```bash
cd backend
python manage.py test accounts.tests.AuthApiTests -v 2
```

### Run Backend Checks
```bash
cd backend
python manage.py check --deploy
```

### Check Supabase Connection
```bash
cd backend
python manage.py shell

from accounts.supabase_rest_auth import SupabaseJWTAuthentication
auth = SupabaseJWTAuthentication()
# Test with a valid token from logged-in admin user
user_data = auth._fetch_supabase_user("<admin_token>")
print(user_data)
```

---

## Success Criteria

All tests pass when:
- ✅ Backend tests: 5/5 pass (includes 410 for disabled login)
- ✅ Frontend lint: 0 errors
- ✅ Frontend build: webpack success
- ✅ Student user: Logs in → redirects to `/dashboard`
- ✅ Admin user: Logs in → redirects to `/admin` → stays on `/admin`
- ✅ Admin tabs: All accessible without errors
- ✅ Session persistence: Admin page accessible after refresh
- ✅ Metadata sync: Role updates reflected after login
- ✅ Local login: Returns 410 Gone

---

## Notes

- The system is now Supabase-only for authentication
- Local Django user accounts are created on-demand when users log in via Supabase
- Admin role is determined by Supabase metadata, not by local Django creation
- SessionAuthentication is kept for Django admin panel access (if needed)
- No JWT tokens are generated locally; only Supabase tokens are used
