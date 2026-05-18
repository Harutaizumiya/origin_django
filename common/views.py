from django.shortcuts import render
from django.views import View
from rest_framework.exceptions import AuthenticationFailed, NotAuthenticated, PermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.views import APIView

from common.exceptions import ApiError
from common.responses import error_response


class HomePageView(View):
    def get(self, request):
        return render(request, "index.html")


class ServiceAPIView(APIView):
    def handle_exception(self, exc):
        if isinstance(exc, ApiError):
            return error_response(code=exc.code, message=exc.message, status_code=exc.status_code)
        if isinstance(exc, (AuthenticationFailed, NotAuthenticated)):
            return error_response(code=4011, message="unauthenticated", status_code=401)
        if isinstance(exc, PermissionDenied):
            return error_response(code=4031, message="forbidden", status_code=403)
        if isinstance(exc, DRFValidationError):
            return error_response(code=4001, message="validation_error", status_code=400)
        return super().handle_exception(exc)
