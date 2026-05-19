from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from accounts.services import AuthTokenService


class CookieTokenAuthentication(BaseAuthentication):
    def authenticate(self, request):
        token = request.COOKIES.get(settings.AUTH_TOKEN_COOKIE_NAME)
        if not token:
            return None

        auth_token = AuthTokenService.get_valid_auth_token(token)
        if auth_token is None:
            raise AuthenticationFailed("Invalid or expired token")
        return auth_token.user, auth_token

    def authenticate_header(self, request):
        return "Cookie"
