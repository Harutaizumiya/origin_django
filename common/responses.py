from rest_framework.response import Response


def success_response(data, *, status_code=200):
    return Response({"code": 0, "message": "success", "data": data}, status=status_code)


def error_response(*, code: int, message: str, status_code: int):
    return Response({"code": code, "message": message, "data": None}, status=status_code)
