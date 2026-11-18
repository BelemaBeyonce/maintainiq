"""Isolated test configuration; never use this module to serve the application."""

import os
from secrets import token_urlsafe

os.environ.setdefault("DJANGO_SECRET_KEY", token_urlsafe(48))
os.environ["TESTING"] = "true"
os.environ["COOKIE_SECURE"] = "false"
os.environ["DEVELOPMENT_INVITE_LINKS"] = "true"
from .settings import *  # noqa: F403,E402
