# Anthropic API Key Rotation — Bewerbungstracker

> **Read this first if you've never rotated before:**
> Bewerbungstracker is a **multi-user** app, but it does not store user AI
> keys in its own database. All AI traffic routes through
> `ai-provider-service` on the wolfinisoftware VPS (`http://127.0.0.1:8767`
> from this VPS's perspective). That service holds per-user keys
> (Fernet-encrypted) and the system fallback Anthropic key.
>
> Result: there are **three different rotation procedures** depending on
> which key is involved. Skip to [§ Scope of this runbook](#scope-of-this-runbook)
> first — picking the wrong one can drop user credentials.

## TL;DR (system-key rotation)

```bash
ssh ionos-vps
sudo bewerbungen-rotate-anthropic-key
```

The script:
1. Reads the new key from stdin with echo off (no shell history, no `ps`)
2. **Pre-flight tests** the new key against `api.anthropic.com` _before_
   writing anything to disk — a bad key cannot break the service
3. Backs up `/var/www/bewerbungen/.env` (chmod 600)
4. Rewrites only the `ANTHROPIC_API_KEY=…` line via `awk -v`
5. Hash-verifies the rewrite
6. Restarts `bewerbungen.service`
7. Auto-rollbacks if the service fails to come up

## Scope of this runbook

### Today's traffic flow

```
Bewerbungstracker user → Flask app (gunicorn)
                          │
                          ▼
                  services/ai_provider_client.py  (HTTP)
                          │
                          ▼
            ai-provider-service @ wolfinisoftware VPS :8767
                          │
            ┌─────────────┴─────────────┐
            ▼                           ▼
   user has BYOK?              no BYOK?
   → use their key            → use system ANTHROPIC_API_KEY
   (from provider_configs,    (from ai-provider-service's
    Fernet-encrypted)          systemd unit)
            │                           │
            └─────────────┬─────────────┘
                          ▼
                  api.anthropic.com
```

If `ai-provider-service` is **down**, Bewerbungstracker falls back to its
own embedded Anthropic SDK using `ANTHROPIC_API_KEY` from this VPS's
`/var/www/bewerbungen/.env`. That fallback is the only reason this `.env`
key still exists.

### The three kinds of keys

| Key | Storage | Who manages it | Rotation |
|---|---|---|---|
| **Bewerbungstracker `.env` Anthropic key** (legacy fallback only) | `ANTHROPIC_API_KEY=` in `/var/www/bewerbungen/.env` | You (admin) | **This runbook** (`bewerbungen-rotate-anthropic-key`) |
| **Per-user provider keys** | `provider_configs.config_encrypted` on the **wolfinisoftware VPS** (Fernet-encrypted in `/var/www/ai-provider-service/instance/storage.db`) | The user themselves, via Bewerbungstracker → Settings → Providers | User self-service; admin only for emergencies |
| **System Anthropic key on `ai-provider-service`** | `ANTHROPIC_API_KEY=` in `/etc/systemd/system/ai-provider-service.service` | The wolfinisoftware admin | `wolfini-rotate-anthropic-key` — see [wolfinisoftware KEY_ROTATION docs](../../../wolfinisoftware/docs/operations/KEY_ROTATION.md) |

### Picking the right procedure

| Situation | Procedure |
|---|---|
| "I leaked the **Bewerbungstracker fallback** Anthropic key" / routine | **This runbook** |
| "I leaked the **shared system** Anthropic key on `ai-provider-service`" | The wolfinisoftware KEY_ROTATION runbook, not this one |
| "A user wants to rotate **their own** Anthropic / OpenAI / Ollama key" | Bewerbungstracker UI → Settings → Provider — they do it themselves, no admin action needed |
| "A user lost UI access and needs their per-user key wiped" | Admin SQL on the wolfinisoftware VPS — see [§ Per-user key rotation (admin path)](#per-user-key-rotation-admin-path) |
| "The Fernet `MASTER_KEY` on `ai-provider-service` got leaked" | wolfinisoftware KEY_ROTATION § MASTER_KEY rotation — every per-user key in `provider_configs` needs re-encryption |

### About the Phase-B BYOK plan

`docs/superpowers/plans/2026-04-28-job-discovery-phase-b-byok.md` describes
a `user_ai_credentials` table inside Bewerbungstracker's own database. That
plan **predates** the integration with `ai-provider-service`. The practical
effect of the ai-provider-service integration is that the BYOK storage now
lives in `provider_configs` on the wolfinisoftware VPS instead — same
concept, different location. The Phase-B plan should be re-read in light of
this; the AI-Provider-Factory work may be partly or wholly subsumed by
delegating to `ai-provider-service`.

## Where the fallback key lives on this VPS

| Component | Location |
|---|---|
| Configured value | `ANTHROPIC_API_KEY=…` in `/var/www/bewerbungen/.env` |
| Loaded by | `bewerbungen.service` via `source /var/www/bewerbungen/.env && exec gunicorn …` |
| File perms | 600 root:root |
| Read at runtime by | `services/cover_letter_service.py` only — and only on the **fallback** code path when `ai-provider-service` is unreachable |

In normal operation, every Claude call from Bewerbungstracker goes via
`services/ai_provider_client.py` → `ai-provider-service` on the
wolfinisoftware VPS. That service holds the **system Anthropic key** (a
*different* key from the one in this `.env`) and serves it to allowlisted
user_ids without a BYOK.

So rotating this key only affects the legacy fallback. If you've already
done the wolfinisoftware-VPS rotation, you're already mostly safe. This
rotation closes the second exposure point on the Bewerbungstracker host
itself.

The other services on this VPS (`email-service`, `imap-proxy`,
`bewerbungen-backup`) don't read the Anthropic key — only `bewerbungen.service`
needs to be restarted on rotation.

## When to rotate

- Routine: every 6 months
- Suspected exposure (key in chat logs, git history, screenshots, public
  Pastebin, etc.)
- Project gets its own key after previously sharing one with another project
- Anthropic Console flags suspicious activity

## Procedure

### 1. Generate the new key

In the [Anthropic Console → API Keys](https://console.anthropic.com/settings/keys):

- Click **Create Key**
- Name it explicitly: `bewerbungstracker-prod` (or `bewerbungstracker-prod-2026-05`)
- Copy the `sk-ant-api03-…` value once — Anthropic only shows it once
- **Do not delete the old key yet**

### 2. Rotate on the VPS

```bash
ssh ionos-vps
sudo bewerbungen-rotate-anthropic-key
```

Expected output:

```
Current key fingerprint: sha256:abcdef0123456789  (…wAAA)

Paste the NEW Anthropic API key (input is hidden, ENTER to submit):
[paste, press Enter]

New key fingerprint:     sha256:fedcba9876543210  (…xBBB)

Pre-flight test: validating new key against api.anthropic.com …
✓ Pre-flight OK (Anthropic accepted the key).

Rotate to this key and restart bewerbungen.service? [y/N] y
Backup saved: /var/www/bewerbungen/.env.bak-YYYYMMDD-HHMMSS  (chmod 600)
Env file updated (mode 600, owner 0:0).
Restarting bewerbungen.service …
✓ bewerbungen.service is active.
Local gunicorn: http://127.0.0.1:5000/ → HTTP 200

Done.
```

### 3. Verify in the app

Open the Bewerbungstracker UI in a browser, log in, and trigger something
that hits Claude — the most reliable smoke test is **Cover Letter
generation** or **CV comparison**, since those run Claude inline and surface
errors immediately.

If everything works, the new key is doing real work against Anthropic.

### 4. Revoke (disable, don't delete) the old key

In the Anthropic Console:

- **Disable** the old key — keeps it visible in the Usage dashboard for
  historical cost reporting
- Don't **Delete** — that removes it from the filter dropdown and makes
  historical cost attribution harder

If you must delete, take a Usage screenshot first.

### 5. Clean up the backup

Once 24h+ have passed without issues:

```bash
ssh ionos-vps
sudo rm /var/www/bewerbungen/.env.bak-*
```

## Recovery

### Pre-flight failed

The most common cause: the key was copied with a leading/trailing space, or
it's already disabled in the Anthropic Console. The script will show the
HTTP status and the first 300 chars of Anthropic's response — that tells
you exactly what went wrong.

Nothing was written to disk. Just re-run.

### Service won't start after rotation

The script auto-rollbacks. If for some reason it didn't:

```bash
ssh ionos-vps
sudo ls /var/www/bewerbungen/.env.bak-*
sudo cp /var/www/bewerbungen/.env.bak-YYYYMMDD-HHMMSS /var/www/bewerbungen/.env
sudo chmod 600 /var/www/bewerbungen/.env
sudo chown root:root /var/www/bewerbungen/.env
sudo systemctl restart bewerbungen
sudo journalctl -u bewerbungen -n 30 --no-pager
```

### Wrong key got rotated in

The pre-flight test would have caught most cases (wrong key = invalid =
Anthropic rejects). But if Anthropic accepted a valid-but-wrong key:

1. Disable the just-rotated key in the Anthropic Console immediately
2. Restore from backup (see above)
3. Re-run rotation with the correct key

### Verifying which key is currently active without exposing it

```bash
ssh ionos-vps
sudo grep -oP '^ANTHROPIC_API_KEY=\K.*' /var/www/bewerbungen/.env \
    | tr -d '\n' | sha256sum | cut -c1-16
```

This prints only the 16-char fingerprint.

## Source

- Live script on VPS: `/usr/local/bin/bewerbungen-rotate-anthropic-key`
- Version-controlled copy: `deploy/scripts/bewerbungen-rotate-anthropic-key.sh`

Re-deploying the script after edits:

```bash
scp deploy/scripts/bewerbungen-rotate-anthropic-key.sh ionos-vps:/tmp/
ssh ionos-vps "sudo install -o root -g root -m 755 \
    /tmp/bewerbungen-rotate-anthropic-key.sh \
    /usr/local/bin/bewerbungen-rotate-anthropic-key && \
    rm /tmp/bewerbungen-rotate-anthropic-key.sh"
```

## Why the pre-flight test matters

The wolfinisoftware rotation script does *not* have a pre-flight test —
that's intentional, because there the `ai-provider-service` has Ollama as
its primary path. If the Claude key is bad, only the fallback path breaks,
and the service still serves traffic.

Bewerbungstracker calls Claude directly. If a bad key gets written, the
service starts fine (systemd is happy, gunicorn binds the port) but **every
Cover Letter / CV operation fails at request time** with cryptic errors.
The pre-flight test pays one extra ~10-token Claude request to guarantee
this never happens.

## Per-user key rotation (admin path)

> **Most of the time: do nothing.** Bewerbungstracker users rotate their own
> keys via Settings → Providers. That writes through HTTP to
> `ai-provider-service` on the wolfinisoftware VPS, which Fernet-encrypts and
> stores in `provider_configs`. No admin action, no SSH, no service restart.

You should only need admin intervention in two cases:

### 1. A user reports a compromised key but can't reach the UI

Null out their per-user config row on the **wolfinisoftware VPS** (per-user
keys do NOT live in Bewerbungstracker's own DB — they live in
`ai-provider-service`'s storage):

```bash
ssh ionos-vps
sudo sqlite3 /var/www/ai-provider-service/instance/storage.db
```

```sql
-- See what user has configured (no plaintext exposure - ciphertext only):
SELECT id, provider_id, length(config_encrypted) AS cipher_bytes
FROM provider_configs WHERE user_id = '<bewerbungstracker-user-id>';

-- Wipe their Claude key:
DELETE FROM provider_configs
WHERE user_id = '<bewerbungstracker-user-id>' AND provider_id = 'claude';
```

The next request from that user falls back to the system key (if the
allowlist permits) or returns a clean error. Tell the user to log into
Bewerbungstracker and re-add a fresh key in Settings.

No service restart needed — the in-memory key cache flushes on its TTL
(default 5 min). Force-flush with `sudo systemctl restart ai-provider-service`.

### 2. After a Bewerbungstracker host compromise

If this VPS itself was compromised, **rotate everything that lives here**:

1. This `.env` Anthropic fallback key → **this runbook**
2. SMTP / IMAP credentials in `/var/www/bewerbungen/.env` → app docs
3. The `AI_PROVIDER_SERVICE_TOKEN` in `/var/www/bewerbungen/.env` → regenerate
   on `ai-provider-service` side, update here

Per-user Anthropic keys held by `ai-provider-service` on the **other** VPS
are unaffected by *this* host's compromise. They only need rotation if the
wolfinisoftware VPS gets compromised instead.

### What never happens

User-provided keys are **never** logged by Bewerbungstracker, **never**
stored in this app's own database, **never** appear in `/var/log/bewerbungen/`,
and **never** appear in journalctl output for `bewerbungen.service`. If you
see one in a log, that's a bug — file an issue immediately.
