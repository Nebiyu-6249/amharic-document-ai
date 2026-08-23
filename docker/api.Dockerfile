# API image. Contains NO machine-learning dependencies (ADR-0007 / control C-45);
# CI fails the build if the lockfile ever gains one.
# Base image is a build arg so a mirrored registry can be substituted in
# air-gapped or policy-restricted CI. Default is the upstream slim image.
ARG BASE_IMAGE=python:3.11-slim
FROM ${BASE_IMAGE} AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN adduser --system --group --no-create-home --uid 10001 adai

WORKDIR /app

# Dependencies first, so the layer caches independently of source changes.
COPY requirements/api.lock.txt /app/requirements/api.lock.txt
RUN pip install --no-cache-dir -r requirements/api.lock.txt

COPY pyproject.toml README.md /app/
COPY src /app/src
COPY migrations /app/migrations
COPY alembic.ini /app/
RUN pip install --no-cache-dir --no-deps -e .

# Blob root lives outside any web-served path (control C-30).
RUN mkdir -p /var/lib/adai/blobs && chown -R adai:adai /var/lib/adai

USER adai
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).status==200 else 1)"

CMD ["uvicorn", "adai.api.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*", \
     "--no-server-header", "--no-date-header"]
