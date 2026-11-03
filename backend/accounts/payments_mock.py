"""Local mock payment provider (no network, no money).

Enabled only when ``settings.PAYMENTS_MOCK`` is true, which requires
``DEBUG=True`` and ``PAYMENTS_MODE=mock``. It mirrors the parts of the
Razorpay SDK the app uses:

* ``client.order.create(data)``            -> {'id': 'order_mock_…', 'amount', 'currency'}
* ``client.utility.verify_payment_signature`` -> same HMAC-SHA256 scheme as Razorpay
  (``hex(hmac(key_secret, f"{order_id}|{payment_id}"))``)

``MockCheckoutView`` plays the role of Razorpay's checkout popup: it returns
the ``razorpay_payment_id`` / ``razorpay_signature`` pair the frontend then
submits to the normal ``/subscribe/verify/`` endpoint, so the real
verification and activation code paths are exercised end to end.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets

from django.conf import settings
from django.http import Http404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView


def payments_mock_enabled() -> bool:
    return bool(getattr(settings, 'PAYMENTS_MOCK', False))


def sign_payment(order_id: str, payment_id: str, key_secret: str) -> str:
    return hmac.new(key_secret.encode('utf-8'), f'{order_id}|{payment_id}'.encode('utf-8'), hashlib.sha256).hexdigest()


class _MockOrders:
    def create(self, data=None, **_kwargs):
        data = data or {}
        return {
            'id': f'order_mock_{secrets.token_hex(8)}',
            'amount': int(data.get('amount', 0)),
            'currency': data.get('currency', 'INR'),
            'status': 'created',
            'notes': data.get('notes', {}),
        }


class _MockUtility:
    def __init__(self, key_secret: str):
        self._key_secret = key_secret

    def verify_payment_signature(self, params):
        expected = sign_payment(params.get('razorpay_order_id', ''), params.get('razorpay_payment_id', ''), self._key_secret)
        if not hmac.compare_digest(expected, str(params.get('razorpay_signature', ''))):
            raise ValueError('Razorpay signature verification failed (mock)')
        return True


class MockRazorpayClient:
    def __init__(self, auth):
        self.order = _MockOrders()
        self.utility = _MockUtility(auth[1])


def get_razorpay_client(key_id: str, key_secret: str):
    """Real Razorpay client in production; the mock only when explicitly enabled locally."""
    if payments_mock_enabled():
        return MockRazorpayClient(auth=(key_id, key_secret))
    import razorpay

    return razorpay.Client(auth=(key_id, key_secret))


class MockCheckoutView(APIView):
    """POST {order_id} -> simulated successful Razorpay checkout response."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if not payments_mock_enabled():
            raise Http404
        import os

        from .models import PaymentAttempt

        order_id = str(request.data.get('order_id') or '').strip()
        attempt = PaymentAttempt.objects.filter(razorpay_order_id=order_id, user=request.user).first()
        if attempt is None:
            return Response({'error': 'Unknown order.'}, status=status.HTTP_404_NOT_FOUND)
        if attempt.status == 'successful':
            return Response({'error': 'Order already paid.'}, status=status.HTTP_409_CONFLICT)
        key_secret = os.getenv('RAZORPAY_KEY_SECRET', '')
        payment_id = f'pay_mock_{secrets.token_hex(8)}'
        return Response({
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': sign_payment(order_id, payment_id, key_secret),
        })
