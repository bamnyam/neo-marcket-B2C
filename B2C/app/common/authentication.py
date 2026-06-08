import base64
import hashlib
import hmac
import json
import uuid

from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from app.buyers.models import Buyer


class BuyerJWTAuthentication(BaseAuthentication):
    AUTH_HEADER_PREFIX = "Bearer "

    def authenticate(self, request):
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return None

        if not auth_header.startswith(self.AUTH_HEADER_PREFIX):
            raise AuthenticationFailed("Invalid authorization header")

        token = auth_header.removeprefix(self.AUTH_HEADER_PREFIX).strip()
        payload = self._decode_hs256_token(token)
        buyer_uuid = payload.get("sub") or payload.get("user_id") or payload.get("buyer_id")

        if not buyer_uuid:
            raise AuthenticationFailed("user_id claim is required")

        try:
            buyer_uuid = uuid.UUID(str(buyer_uuid))
        except ValueError as exc:
            raise AuthenticationFailed("user_id claim must be a UUID") from exc

        try:
            buyer = Buyer.objects.get(uuid=buyer_uuid, is_active=True, deleted=False)
        except Buyer.DoesNotExist as exc:
            raise AuthenticationFailed("Buyer not found") from exc

        return buyer, payload

    def authenticate_header(self, request):
        return "Bearer"

    def _decode_hs256_token(self, token):
        parts = token.split(".")

        if len(parts) != 3:
            raise AuthenticationFailed("Invalid token")

        header = self._decode_json_part(parts[0])

        if header.get("alg") != "HS256":
            raise AuthenticationFailed("Unsupported token algorithm")

        expected = hmac.new(
            settings.SECRET_KEY.encode(),
            msg=f"{parts[0]}.{parts[1]}".encode(),
            digestmod=hashlib.sha256,
        ).digest()

        if not hmac.compare_digest(self._b64encode(expected), parts[2]):
            raise AuthenticationFailed("Invalid token signature")

        return self._decode_json_part(parts[1])

    def _decode_json_part(self, value):
        try:
            decoded = base64.urlsafe_b64decode(self._pad_b64(value)).decode()
            return json.loads(decoded)
        except (ValueError, json.JSONDecodeError) as exc:
            raise AuthenticationFailed("Invalid token") from exc

    def _b64encode(self, value):
        return base64.urlsafe_b64encode(value).decode().rstrip("=")

    def _pad_b64(self, value):
        return value + "=" * (-len(value) % 4)
