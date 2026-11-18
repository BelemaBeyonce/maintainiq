import json
import logging
from time import perf_counter
from uuid import uuid4

from django.http import JsonResponse


class JsonFormatter(logging.Formatter):
    def format(self, record):
        data = {"level": record.levelname, "event": record.getMessage()}
        for key in ("request_id", "status", "duration_ms", "method"):
            if hasattr(record, key):
                data[key] = getattr(record, key)
        return json.dumps(data)


class RequestContext:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = str(uuid4())
        start = perf_counter()
        try:
            length = int(request.META.get("CONTENT_LENGTH") or 0)
        except ValueError:
            length = -1
        if length < 0 or length > 262144:
            response = JsonResponse(
                {
                    "error": {
                        "code": "request_limit",
                        "message": "Invalid or oversized request body",
                        "details": {},
                        "request_id": request.request_id,
                    }
                },
                status=413,
            )
        else:
            response = self.get_response(request)
        response["X-Request-ID"] = request.request_id
        logging.getLogger("maintainiq").info(
            "request_complete",
            extra={
                "request_id": request.request_id,
                "status": response.status_code,
                "method": request.method,
                "duration_ms": round((perf_counter() - start) * 1000, 2),
            },
        )
        return response
