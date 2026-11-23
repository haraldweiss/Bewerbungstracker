# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
#
# Multi-stage build for Bewerbungstracker.
# Based on python:3.12-slim (glibc 2.36+) for cryptography native bindings.
# Same pattern as ai-provider-service.

# Build natively on the same Python/Debian base as the runtime stage.
FROM docker.io/library/python:3.12-slim AS crypto-builder
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential pkg-config libffi-dev rustc cargo perl curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*
COPY security/cryptography/build-wheel.sh /usr/local/bin/build-crypto-wheel
RUN bash /usr/local/bin/build-crypto-wheel 50.0.2 /crypto-build

FROM docker.io/library/python:3.12-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# supercronic for cron container (single-binary)
ARG SUPERCRONIC_VERSION=0.2.33
ADD https://github.com/aptible/supercronic/releases/download/v${SUPERCRONIC_VERSION}/supercronic-linux-arm64 \
    /usr/local/bin/supercronic
RUN chmod +x /usr/local/bin/supercronic

WORKDIR /app

COPY requirements.txt ./
COPY security/cryptography/constraints.txt security/cryptography/verify-runtime.py /opt/cryptography/
COPY --from=crypto-builder /crypto-build/wheels/ /opt/crypto-wheels/
RUN pip install --no-cache-dir -c /opt/cryptography/constraints.txt -r requirements.txt && \
    (cd /opt/crypto-wheels && sha256sum --check SHA256SUMS) && \
    pip install --no-cache-dir --no-index --no-deps --force-reinstall /opt/crypto-wheels/*.whl && \
    python /opt/cryptography/verify-runtime.py --expected-cryptography 50.0.2 && \
    pip check && \
    rm -rf /opt/crypto-wheels

COPY . .

RUN mkdir -p /app/data /app/instance /app/logs

RUN chmod +x docker-entrypoint.sh

EXPOSE 5000 8765 8766

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["app"]
