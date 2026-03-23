#!/usr/bin/env python
"""Test password reset with console email backend"""
import os
import sys
import django

# Set up Django with console email backend for testing
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')
os.environ['EMAIL_HOST_PASSWORD'] = ''  # Force console backend

django.setup()

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from accounts.views import send_password_reset_email

User = get_user_model()

print("=" * 70)
print("PASSWORD RESET TEST - CONSOLE EMAIL BACKEND")
print("=" * 70)
print(f"\nEmail Backend: {settings.EMAIL_BACKEND}")

# Test password reset
email = "testuser123@test.com"
try:
    user = User.objects.filter(email=email).first()
    if not user:
        print(f"Creating test user with email: {email}")
        user = User.objects.create_user(
            username="consoletest_" + str(User.objects.count()),
            email=email,
            password="TestPass123!",
            first_name="Console",
            last_name="Test"
        )
    
    print(f"\n✓ User: {user.username} ({user.email})")
    
    # Generate reset token
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    reset_link = f"http://localhost:3000/reset-password?uid={uid}&token={token}"
    
    print(f"✓ Reset link generated:")
    print(f"  {reset_link}")
    
    # Send email (should print to console with console backend)
    print(f"\nSending reset email via {settings.EMAIL_BACKEND}...")
    print("-" * 70)
    try:
        send_password_reset_email(user, reset_link)
        print("-" * 70)
        print("✓ Email sent successfully!")
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        
except Exception as e:
    print(f"✗ Test failed: {e}")
    import traceback
    traceback.print_exc()
