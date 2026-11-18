FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY backend/requirements.lock ./
RUN --mount=type=secret,id=pip_ca \
    if [ -f /run/secrets/pip_ca ]; then export PIP_CERT=/run/secrets/pip_ca; fi; \
    pip install -r requirements.lock
RUN groupadd --gid 10001 maintainiq && useradd --uid 10001 --gid maintainiq maintainiq && mkdir /data && chown maintainiq:maintainiq /data
COPY --chown=maintainiq:maintainiq backend/config ./config
COPY --chown=maintainiq:maintainiq backend/core ./core
COPY --chown=maintainiq:maintainiq backend/manage.py ./
COPY --chown=maintainiq:maintainiq infra/backend-start.sh ./backend-start.sh
USER maintainiq
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health/',timeout=3)"
CMD ["sh", "backend-start.sh"]
