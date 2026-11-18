import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_handler


def exception_handler(exc, context):
    if isinstance(exc, DjangoValidationError):
        exc = ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
    if isinstance(exc, IntegrityError):
        return Response(
            {
                "error": {
                    "code": "conflict",
                    "message": "The change conflicts with an existing record or relationship",
                    "details": {},
                    "request_id": getattr(context["request"], "request_id", None),
                }
            },
            status=409,
        )
    response = drf_handler(exc, context)
    if response is None:
        logging.getLogger("maintainiq").error(
            "request_failure", extra={"request_id": getattr(context["request"], "request_id", None)}
        )
        response = Response({"detail": "An unexpected error occurred"}, status=500)
    response.data = {
        "error": {
            "code": str(getattr(exc, "default_code", "request_error")),
            "message": "Request failed",
            "details": response.data,
            "request_id": getattr(context["request"], "request_id", None),
        }
    }
    return response


def csrf_failure(request, reason=""):
    from django.http import JsonResponse

    return JsonResponse(
        {
            "error": {
                "code": "csrf_failed",
                "message": "CSRF verification failed. Reload and try again.",
                "details": {},
                "request_id": getattr(request, "request_id", None),
            }
        },
        status=403,
    )
