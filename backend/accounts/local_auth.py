"""Dev-only email/password authentication for running CrackLabs locally.

Production authentication is Supabase-only. For a fully local stack (no
Supabase project) set ``LOCAL_DEV_AUTH=1`` together with ``DEBUG=True``;
``settings.LOCAL_DEV_AUTH`` is forced to False whenever DEBUG is off, so
these endpoints and the token authenticator can never be active in
production.

Endpoints (mounted under /api/auth/local/ only when enabled):
  POST login/     {email|username, password}  -> {access, refresh, user}
  POST register/  {email, username?, password, first_name?, last_name?}
  POST refresh/   {refresh}                    -> {access, refresh?}

With AUTH_PROVIDER=django the tokens are Django-native sessions
(accounts.native_sessions: a ``session_id`` claim, server-side rotation and
revocation, the device cap) and NativeJWTAuthentication checks them, so a
NEXT_PUBLIC_AUTH_MODE=local build runs against a django-mode backend too;
accounts registered here are marked email-verified (dev only).
"""
from __future__ import annotations

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.http import Http404
from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

User = get_user_model()


from .local_auth_authentication import LocalDevJWTAuthentication, local_auth_enabled  # noqa: E402,F401


class _LocalOnlyMixin:
    permission_classes = [permissions.AllowAny]
    authentication_classes: list = []

    def initial(self, request, *args, **kwargs):
        # Defence in depth: the URLs are only mounted when enabled, but the
        # views refuse to run otherwise as well.
        if not local_auth_enabled():
            raise Http404
        return super().initial(request, *args, **kwargs)


def _token_payload(user, request=None):
    from .auth_mode import django_auth_enabled
    from .serializers import UserSerializer

    if django_auth_enabled():
        from .native_sessions import issue_session_tokens

        tokens = issue_session_tokens(user, request, 'local')
        return {**tokens, 'user': UserSerializer(user).data}
    refresh = RefreshToken.for_user(user)
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'user': UserSerializer(user).data,
    }


class LocalLoginView(_LocalOnlyMixin, APIView):
    throttle_scope = 'local_auth'

    def post(self, request):
        identifier = str(request.data.get('email') or request.data.get('username') or '').strip()
        password = str(request.data.get('password') or '')
        if not identifier or not password:
            return Response({'error': 'Email and password are required.'}, status=status.HTTP_400_BAD_REQUEST)

        username = identifier
        if '@' in identifier:
            match = User.objects.filter(email__iexact=identifier).only('username').first()
            if match is not None:
                username = match.username
        # Goes through django-axes (AxesStandaloneBackend) for lockout.
        user = authenticate(request=request, username=username, password=password)
        if user is None:
            return Response({'error': 'Invalid email or password.'}, status=status.HTTP_401_UNAUTHORIZED)
        if not user.is_active:
            return Response({'error': 'This account is disabled.'}, status=status.HTTP_403_FORBIDDEN)
        return Response(_token_payload(user, request))


class _LocalRegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    username = serializers.CharField(max_length=150, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('An account with this email already exists.')
        return value

    def validate(self, data):
        from .handles import username_for_new_account

        validate_password(data['password'])
        # Public (discussions, leaderboard): the chosen name when it follows the
        # Settings rules (3-30 letters, digits, _ or ., not a team name), made
        # unique, or a generated learner_<hex> handle -- never the email's
        # local part. Accounts made here are always students.
        data['username'] = username_for_new_account(User, data.get('username'), data['email'])
        return data


class LocalRegisterView(_LocalOnlyMixin, APIView):
    throttle_scope = 'local_auth'

    def post(self, request):
        serializer = _LocalRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        from .models import TokenBalance

        with transaction.atomic():
            user = User.objects.create_user(
                username=data['username'],
                email=data['email'],
                password=data['password'],
                first_name=data.get('first_name', ''),
                last_name=data.get('last_name', ''),
            )
            # Role is never client-controlled.
            if getattr(user, 'role', 'student') != 'student':
                user.role = 'student'
                user.save(update_fields=['role'])
            from .auth_mode import django_auth_enabled

            if django_auth_enabled():
                # Dev only (DEBUG): native sessions need a verified email.
                from django.utils import timezone

                user.email_verified_at = timezone.now()
                user.save(update_fields=['email_verified_at'])
            TokenBalance.objects.get_or_create(user=user)
        return Response(_token_payload(user, request), status=status.HTTP_201_CREATED)


class LocalRefreshView(_LocalOnlyMixin, TokenRefreshView):
    def post(self, request, *args, **kwargs):
        from .auth_mode import django_auth_enabled

        if django_auth_enabled():
            from .native_sessions import NativeAuthError, rotate

            try:
                return Response(rotate(request.data.get('refresh') if hasattr(request.data, 'get') else None))
            except NativeAuthError as exc:
                return exc.response()
        return super().post(request, *args, **kwargs)
