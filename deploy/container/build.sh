#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
#
# Baut das Bewerbungstracker-Image und taggt es MIT EINER VERSION, nicht nur
# :latest. Grund (Session 2026-06-12): mit nacktem :latest ist "was laeuft"
# nicht eindeutig und ein Rollback unmoeglich. Mit einem SHA-/Versions-Tag gilt:
#   - eindeutig nachvollziehbar, welcher Stand laeuft
#   - Rollback = IMAGE_TAG=<alter-tag> setup-oracle-vm.sh rebuild
#
# Verwendung:
#   ./build.sh                 # Tag = git short-SHA (oder Timestamp ohne .git)
#   ./build.sh 437015d         # expliziter Tag (z.B. beim Build aus git archive)
#
# Baut immer zusaetzlich :latest (= zuletzt gebauter Stand).

set -euo pipefail

IMAGE_REPO="localhost/bewerbungen"

# Build-Kontext = Repo-Root (zwei Ebenen ueber deploy/container/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTEXT="$SCRIPT_DIR/../.."

# Tag-Quelle: Argument > git short-SHA > Timestamp
if [ "${1:-}" != "" ]; then
    TAG="$1"
elif git -C "$CONTEXT" rev-parse --short HEAD >/dev/null 2>&1; then
    TAG="$(git -C "$CONTEXT" rev-parse --short HEAD)"
else
    TAG="$(date +%Y%m%d-%H%M%S)"
fi

echo "▶ Baue $IMAGE_REPO:$TAG (+ :latest)"
docker build -t "$IMAGE_REPO:$TAG" -t "$IMAGE_REPO:latest" "$CONTEXT"

echo "✓ Gebaut:"
echo "    $IMAGE_REPO:$TAG"
echo "    $IMAGE_REPO:latest"
echo ""
echo "  Deploy mit diesem Stand:   IMAGE_TAG=$TAG $SCRIPT_DIR/setup-oracle-vm.sh rebuild"
echo "  Rollback auf alten Stand:  IMAGE_TAG=<alter-tag> $SCRIPT_DIR/setup-oracle-vm.sh rebuild"
