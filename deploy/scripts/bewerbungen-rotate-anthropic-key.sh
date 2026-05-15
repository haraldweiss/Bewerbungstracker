#!/bin/bash
# Rotate ANTHROPIC_API_KEY for Bewerbungstracker (/var/www/bewerbungen/.env).
# Usage:  sudo bewerbungen-rotate-anthropic-key
#
# - Reads the new key from stdin with echo OFF (no shell history, no ps).
# - Pre-flight-tests the new key against api.anthropic.com BEFORE writing it
#   to disk, so a bad key cannot break the service.
# - Backs up the .env, rewrites only the ANTHROPIC_API_KEY line, restarts
#   bewerbungen.service, and rolls back automatically on failure.

set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "Must be run as root.  Try: sudo $0" >&2
    exit 1
fi

ENV_FILE="/var/www/bewerbungen/.env"
SERVICE="bewerbungen"
KEY_NAME="ANTHROPIC_API_KEY"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "Env file not found: $ENV_FILE" >&2
    exit 1
fi

# --- show current key fingerprint (no value) -------------------------------
CUR_KEY=$(grep -oP "^${KEY_NAME}=\K.*" "$ENV_FILE" || true)
# strip optional surrounding quotes
CUR_KEY="${CUR_KEY%\"}"; CUR_KEY="${CUR_KEY#\"}"
CUR_KEY="${CUR_KEY%\'}"; CUR_KEY="${CUR_KEY#\'}"

if [[ -n "$CUR_KEY" ]]; then
    CUR_HASH=$(printf '%s' "$CUR_KEY" | sha256sum | cut -c1-16)
    CUR_TAIL="${CUR_KEY: -4}"
    echo "Current key fingerprint: sha256:${CUR_HASH}  (…${CUR_TAIL})"
else
    echo "No current key found in $ENV_FILE (will be added)."
fi

# --- read new key, hidden ---------------------------------------------------
echo
echo "Paste the NEW Anthropic API key (input is hidden, ENTER to submit):"
read -rs NEW_KEY
echo

if [[ -z "$NEW_KEY" ]]; then
    echo "No input — aborted." >&2
    exit 2
fi

if [[ ! "$NEW_KEY" =~ ^sk-ant-api03-[A-Za-z0-9_-]{80,}$ ]]; then
    echo "Error: doesn't look like an Anthropic key (expected sk-ant-api03-…)." >&2
    exit 2
fi

if [[ "$NEW_KEY" == "$CUR_KEY" ]]; then
    echo "New key is identical to current key — nothing to do." >&2
    exit 0
fi

NEW_HASH=$(printf '%s' "$NEW_KEY" | sha256sum | cut -c1-16)
NEW_TAIL="${NEW_KEY: -4}"
echo "New key fingerprint:     sha256:${NEW_HASH}  (…${NEW_TAIL})"

# --- pre-flight: ask Anthropic directly whether this key is valid ----------
# Tiny request (~10 tokens) — proves the key is accepted before we touch disk.
echo
echo "Pre-flight test: validating new key against api.anthropic.com …"
PREFLIGHT=$(curl -s -m 15 -o /tmp/anth-preflight.$$.json -w '%{http_code}' \
    https://api.anthropic.com/v1/messages \
    -H "x-api-key: ${NEW_KEY}" \
    -H "anthropic-version: 2023-06-01" \
    -H "content-type: application/json" \
    --data-raw '{"model":"claude-haiku-4-5-20251001","max_tokens":10,"messages":[{"role":"user","content":"Reply OK"}]}' \
    || echo "000")
PREFLIGHT_BODY=$(cat /tmp/anth-preflight.$$.json 2>/dev/null || echo "")
rm -f /tmp/anth-preflight.$$.json

if [[ "$PREFLIGHT" != "200" ]]; then
    echo "✗ Pre-flight FAILED: HTTP $PREFLIGHT" >&2
    echo "Response (first 300 chars): ${PREFLIGHT_BODY:0:300}" >&2
    echo "Aborting — nothing written to disk, service untouched." >&2
    exit 5
fi
echo "✓ Pre-flight OK (Anthropic accepted the key)."

# --- confirm ----------------------------------------------------------------
echo
read -rp "Rotate to this key and restart ${SERVICE}.service? [y/N] " CONFIRM
if [[ ! "$CONFIRM" =~ ^[yYjJ]$ ]]; then
    echo "Aborted."
    exit 0
fi

# --- backup -----------------------------------------------------------------
TS=$(date +%Y%m%d-%H%M%S)
BACKUP="${ENV_FILE}.bak-${TS}"
cp -p "$ENV_FILE" "$BACKUP"
chmod 600 "$BACKUP"
echo "Backup saved: $BACKUP  (chmod 600)"

# --- rewrite the key line ---------------------------------------------------
TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT

if grep -q "^${KEY_NAME}=" "$ENV_FILE"; then
    # Replace existing line.  awk -v keeps the key out of regex parsing.
    awk -v keyname="$KEY_NAME" -v key="$NEW_KEY" '
        $0 ~ "^" keyname "=" {
            printf "%s=%s\n", keyname, key
            next
        }
        { print }
    ' "$ENV_FILE" > "$TMP"
else
    # Append if not present yet.
    cp "$ENV_FILE" "$TMP"
    printf '%s=%s\n' "$KEY_NAME" "$NEW_KEY" >> "$TMP"
fi

# Sanity check: line is there
if ! grep -q "^${KEY_NAME}=" "$TMP"; then
    echo "ERROR: rewrite would lose the key line.  Aborting, original untouched." >&2
    exit 3
fi

# Sanity check: the value matches our new key (strip trailing newline from grep output!)
WROTE_KEY=$(grep -oP "^${KEY_NAME}=\K.*" "$TMP" | tr -d '\n')
WROTE_KEY="${WROTE_KEY%\"}"; WROTE_KEY="${WROTE_KEY#\"}"
WROTE_KEY="${WROTE_KEY%\'}"; WROTE_KEY="${WROTE_KEY#\'}"
WROTE_HASH=$(printf '%s' "$WROTE_KEY" | sha256sum | cut -c1-16)

if [[ "$WROTE_HASH" != "$NEW_HASH" ]]; then
    echo "ERROR: hash mismatch after rewrite — aborting." >&2
    exit 3
fi

# Preserve perms+owner of the original (which was -rw------- root:root).
ORIG_MODE=$(stat -c '%a' "$ENV_FILE")
ORIG_OWNER=$(stat -c '%u:%g' "$ENV_FILE")
install -m "$ORIG_MODE" "$TMP" "$ENV_FILE"
chown "$ORIG_OWNER" "$ENV_FILE"
echo "Env file updated (mode $ORIG_MODE, owner $ORIG_OWNER)."

# --- restart bewerbungen.service -------------------------------------------
echo "Restarting ${SERVICE}.service …"
systemctl restart "${SERVICE}.service"
sleep 3

if ! systemctl is-active --quiet "${SERVICE}.service"; then
    echo "✗ ${SERVICE}.service failed to start.  Rolling back …" >&2
    cp -p "$BACKUP" "$ENV_FILE"
    chmod "$ORIG_MODE" "$ENV_FILE"
    chown "$ORIG_OWNER" "$ENV_FILE"
    systemctl restart "${SERVICE}.service" || true
    echo "Last log lines:" >&2
    journalctl -u "${SERVICE}.service" -n 20 --no-pager >&2 || true
    exit 4
fi

echo "✓ ${SERVICE}.service is active."

# --- optional: quick reachability check on local gunicorn port -------------
LOCAL_PORT=$(grep -oP -- '--bind\s+127\.0\.0\.1:\K[0-9]+' /etc/systemd/system/${SERVICE}.service 2>/dev/null || echo "5000")
HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' -m 5 "http://127.0.0.1:${LOCAL_PORT}/" || echo "000")
echo "Local gunicorn: http://127.0.0.1:${LOCAL_PORT}/ → HTTP ${HTTP_CODE}"

echo
echo "Done.  Old key is no longer referenced by the running service."
echo "Backup: $BACKUP  (delete manually once you've confirmed everything works)"
