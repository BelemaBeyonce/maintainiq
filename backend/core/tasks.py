import logging

from celery import shared_task
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from core.models import User


@shared_task(bind=True, max_retries=3)
def send_password_reset(self, email):
    user = User.objects.filter(email__iexact=email, is_active=True).first()
    if user is None:
        return
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    link = f"{settings.FRONTEND_URL}/reset-password#uid={uid}&token={token}"
    try:
        send_mail(
            "Reset your MaintainIQ password",
            f"Use this private, single-use reset link within one hour: {link}",
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
    except Exception:  # noqa: BLE001 - redact transport errors from task failure records
        logging.getLogger("maintainiq").warning("password_reset_delivery_failed")
        raise self.retry(exc=RuntimeError("Mail delivery failed"), countdown=30) from None
