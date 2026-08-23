# Worker image.
#
# Default build uses the api lockfile, which keeps the stub pipeline runnable without
# downloading a multi-gigabyte ML stack. Build with --build-arg LOCKFILE=ml.lock.txt to
# get torch and kraken for the real pipeline.
#
# This image is a separate environment from the api on purpose (ADR-0007): the boundary
# is what keeps a vulnerable decoder off the request path.
# Base image is a build arg so a mirrored registry can be substituted.
ARG BASE_IMAGE=python:3.11-slim
FROM ${BASE_IMAGE}

ARG LOCKFILE=api.lock.txt

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN adduser --system --group --no-create-home --uid 10002 adaiworker

WORKDIR /app

COPY requirements/${LOCKFILE} /app/requirements/lock.txt
RUN pip install --no-cache-dir -r requirements/lock.txt

COPY pyproject.toml README.md /app/
COPY src /app/src
RUN pip install --no-cache-dir --no-deps -e .

RUN mkdir -p /var/lib/adai/blobs && chown -R adaiworker:adaiworker /var/lib/adai

USER adaiworker

CMD ["arq", "adai.worker.main.WorkerSettings"]
