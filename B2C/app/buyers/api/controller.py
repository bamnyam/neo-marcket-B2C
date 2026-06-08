import base64
import hashlib
import hmac
import json
import time
import uuid

from django.conf import settings
from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from app.carts.services import CartService


class LoginController(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")

        if not email or not password:
            return Response(
                {
                    "code": "INVALID_REQUEST",
                    "message": "email and password are required",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        buyer = authenticate(request, username=email, password=password)

        if buyer is None:
            return Response(
                {
                    "code": "UNAUTHORIZED",
                    "message": "Invalid credentials",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        session_id = self._parse_session_id(request)

        if isinstance(session_id, Response):
            return session_id

        if session_id is not None:
            CartService().merge_guest_cart(buyer, session_id)

        return Response(
            {
                "access_token": self._make_token(buyer, token_type="access"),
                "refresh_token": self._make_token(buyer, token_type="refresh"),
                "token_type": "Bearer",
                "expires_in": 3600,
                "user_id": str(buyer.uuid),
            },
            status=status.HTTP_200_OK,
        )

    def _parse_session_id(self, request):
        raw_session_id = request.headers.get("X-Session-Id")

        if not raw_session_id:
            return None

        try:
            return uuid.UUID(str(raw_session_id))
        except ValueError:
            return Response(
                {
                    "code": "INVALID_REQUEST",
                    "message": "X-Session-Id must be a valid UUID",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    def _make_token(self, buyer, token_type):
        now = int(time.time())
        header = {"alg": "HS256", "typ": "JWT"}
        payload = {
            "sub": str(buyer.uuid),
            "user_id": str(buyer.uuid),
            "type": token_type,
            "iat": now,
            "exp": now + 3600,
        }
        encoded_header = self._b64encode(json.dumps(header).encode())
        encoded_payload = self._b64encode(json.dumps(payload).encode())
        signature = hmac.new(
            settings.SECRET_KEY.encode(),
            msg=f"{encoded_header}.{encoded_payload}".encode(),
            digestmod=hashlib.sha256,
        ).digest()

        return f"{encoded_header}.{encoded_payload}.{self._b64encode(signature)}"

    def _b64encode(self, value):
        return base64.urlsafe_b64encode(value).decode().rstrip("=")
