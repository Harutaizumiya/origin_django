from rest_framework.permissions import AllowAny

from accounts.schemas import AuthLoginResultSerializer, AuthUserSerializer, LoginSerializer, LogoutResultSerializer
from accounts.services import AuthTokenService
from common.responses import success_response
from common.views import ServiceAPIView


class LoginView(ServiceAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = AuthTokenService.login(
            request=request,
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
        )
        output = AuthLoginResultSerializer(result)
        return success_response(output.data)


class LogoutView(ServiceAPIView):
    def post(self, request):
        result = AuthTokenService.logout(getattr(request, "auth", None))
        output = LogoutResultSerializer(result)
        return success_response(output.data)


class MeView(ServiceAPIView):
    def get(self, request):
        output = AuthUserSerializer(AuthTokenService.serialize_user(request.user))
        return success_response(output.data)
