"""Dev-only email/password authentication for running CrackLabs locally.

Production authentication is Supabase-only. For a fully local stack (no
Supabase project) set ``LOCAL_DEV_AUTH=1`` together with ``DEBUG=True``;
``settings.LOCAL_DEV_AUTH`` is forced to False whenever DEBUG is off, so
these endpoints and the token authenticator can never be active in
production.

Endpoints (mounted under /api/auth/local/ only when enabled):
  POST login/     {email|username, password}  -> {access, refresh, user}
  POST register/  {email, username, password, first_name?, last_name?}
  POST refresh/   {refresh}                    -> {access, refresh?}
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
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

User = get_user_model()


def local_auth_enabled() -> bool:
    return bool(getattr(settings, 'LOCAL_DEV_AUTH', False))


class LocalDevJWTAuthentication(JWTAuthentication):
    """SimpleJWT bearer auth, active only in local dev mode."""

    def authenticate(self, request):
        if not local_auth_enabled():
            return None
        return super().authenticate(request)


class _LocalOnlyMixin:
    permission_classes = [permissions.AllowAny]
    authentication_classes: list = []

    def initial(self, request, *args, **kwargs):
        # Defence in depth: the URLs are only mounted when enabled, but the
        # views refuse to run otherwise as well.
        if not local_auth_enabled():
            raise Http404
        return super().initial(request, *args, **kwargs)


def _token_payload(user):
    from .serializers import UserSerializer

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
        return Response(_token_payload(user))


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
        username = (data.get('username') or '').strip() or data['email'].split('@')[0]
        base, suffix = username[:140], 1
        while User.objects.filter(username=username).exists():
            suffix += 1
            username = f'{base}_{suffix}'
        data['username'] = username
        validate_password(data['password'])
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
            TokenBalance.objects.get_or_create(user=user)
        return Response(_token_payload(user), status=status.HTTP_201_CREATED)


class LocalRefreshView(_LocalOnlyMixin, TokenRefreshView):
    pass
