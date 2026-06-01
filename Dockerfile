# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
#
# Single-stage build for Bewerbungstracker.
# Based on python:3.12-slim (glibc 2.36+) for cryptography native bindings.
# Same pattern as ai-provider-service.

FROM docker.io/library/python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# supercronic for cron container (single-binary)
ARG SUPERCRONIC_VERSION=0.2.33
ADD https://github.com/aptible/supercronic/releases/download/v${SUPERCRONIC_VERSION}/supercronic-linux-amd64 \
    /usr/local/bin/supercronic
RUN chmod +x /usr/local/bin/supercronic

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data /app/instance /app/logs

RUN chmod +x docker-entrypoint.sh

EXPOSE 5000 8765 8766

# Healthcheck via curl on root (nginx/gunicorn must be up).
# Quadlet files override this with per-service HealthCmd when needed.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD curl -fsS http://127.0.0.1:5000/ || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["app"]
