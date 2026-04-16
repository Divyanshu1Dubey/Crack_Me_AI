# Gmail Setup for Password Reset

CrackCMS uses Gmail SMTP to send password reset emails. Follow these steps to configure it.

## Step 1: Enable 2-Step Verification

1. Go to https://myaccount.google.com/security
2. Under "How you sign in to Google", enable **2-Step Verification**
3. Complete the setup process

## Step 2: Create an App Password

1. Go to https://myaccount.google.com/apppasswords
2. Select **Mail** as the app
3. Select **Other (Custom name)** and enter "CrackCMS"
4. Click **Generate**
5. Copy the 16-character password (e.g., `abcd efgh ijkl mnop`)

## Step 3: Set Environment Variables

### Local Development

Add to your `.env` file in the backend directory:

```env
EMAIL_HOST_USER=crackwith.ai@gmail.com
EMAIL_HOST_PASSWORD=abcd efgh ijkl mnop
FRONTEND_URL=http://localhost:3000
```

### Production (Render)

In Render dashboard → Environment:

```
EMAIL_HOST_USER=crackwith.ai@gmail.com
EMAIL_HOST_PASSWORD=abcd efgh ijkl mnop
FRONTEND_URL=https://your-app.vercel.app
```

## Step 4: Test

1. Start the backend: `python manage.py runserver`
2. Start the frontend: `npm run dev`
3. Go to `/login` → Click "Forgot password?"
4. Enter your email and click "Send Reset Link"
5. Check your inbox for the reset email

## Troubleshooting

- **"Less secure app access"**: Not needed if using App Passwords with 2FA
- **Email not arriving**: Check spam folder. Verify `EMAIL_HOST_PASSWORD` has no extra spaces
- **"SMTPAuthenticationError"**: Regenerate the App Password and update the env var
- **Rate limits**: Gmail allows ~500 emails/day for free accounts
