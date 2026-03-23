#!/usr/bin/env python
"""Test password reset flow"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from accounts.views import send_password_reset_email

User = get_user_model()

# Check users in database
print("=" * 60)
print("CHECKING USERS IN DATABASE")
print("=" * 60)
users = User.objects.all()
for u in users:
    print(f"  Username: {u.username}, Email: {u.email}")

# Test password reset for divyanshudubey2712@gmail.com
print("\n" + "=" * 60)
print("TESTING PASSWORD RESET")
print("=" * 60)
email = "testuser123@test.com"  # Use testuser123 email which is unique
try:
    user = User.objects.filter(email=email).first()
    if not user:
        # Create a new test user
        print(f"Creating new test user with email: {email}")
        user = User.objects.create_user(
            username="resettest_" + str(User.objects.count()),
            email=email,
            password="TestPass123!",
            first_name="Reset",
            last_name="Test"
        )
        print(f"✓ Test user created: {user.username}")
    else:
        print(f"✓ User found: {user.username} ({user.email})")
    
    # Generate reset token
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    reset_link = f"http://localhost:3000/reset-password?uid={uid}&token={token}"
    
    print(f"✓ Reset link generated:")
    print(f"  {reset_link[:80]}...")
    
    # Try to send email
    print(f"\nAttempting to send reset email...")
    try:
        send_password_reset_email(user, reset_link)
        print("✓ Email sent successfully!")
    except Exception as e:
        print(f"✗ Email failed: {e}")
        
except User.DoesNotExist:
    print(f"✗ User not found with email: {email}")
