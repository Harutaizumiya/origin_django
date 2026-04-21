from rest_framework.response import Response


def success_response(data, *, meta=None, status_code=200):
    payload = {"data": data}
    if meta is not None:
        payload["meta"] = meta
    return Response(payload, status=status_code)


def error_response(*, code: str, message: str, status_code: int):
    return Response({"error": {"code": code, "message": message}}, status=status_code)
