from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from accounts.services import AuthTokenService


class BearerTokenAuthentication(BaseAuthentication):
    keyword = b"bearer"

    def authenticate(self, request):
        auth = get_authorization_header(request).split()
        if not auth:
            return None
        if auth[0].lower() != self.keyword:
            return None
        if len(auth) != 2:
            raise AuthenticationFailed("Invalid bearer token header")

        try:
            token = auth[1].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise AuthenticationFailed("Invalid bearer token header") from exc

        auth_token = AuthTokenService.get_valid_auth_token(token)
        if auth_token is None:
            raise AuthenticationFailed("Invalid or expired token")
        return auth_token.user, auth_token

    def authenticate_header(self, request):
        return "Bearer"
