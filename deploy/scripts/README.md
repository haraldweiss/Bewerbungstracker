# Deploy Scripts

Scripts that live on the VPS under `/usr/local/bin/`. Version-controlled here
so they can be reviewed, modified, and redeployed.

| Script | Purpose | Detailed doc |
|---|---|---|
| `bewerbungen-rotate-anthropic-key.sh` | Rotate the Anthropic API key for `bewerbungen.service` with pre-flight validation against api.anthropic.com, atomic rewrite, and auto-rollback | [../../docs/DEPLOYMENT/KEY_ROTATION.md](../../docs/DEPLOYMENT/KEY_ROTATION.md) |

## Deploying a script after edits

```bash
SCRIPT=bewerbungen-rotate-anthropic-key.sh
DEST=${SCRIPT%.sh}

scp deploy/scripts/$SCRIPT ionos-vps:/tmp/
ssh ionos-vps "sudo install -o root -g root -m 755 \
    /tmp/$SCRIPT /usr/local/bin/$DEST && rm /tmp/$SCRIPT"
```

## Conventions

- Scripts run as **root** via `sudo` (they touch `/var/www/bewerbungen/.env`
  and systemd services)
- They check `$EUID -ne 0` and exit early if not root
- They prefer `awk -v` over `sed` for substitution of values that contain
  regex metacharacters (API keys, paths, URLs, …)
- They back up before writing, and roll back if the post-action health
  check fails
- They never echo or log the full secret value — only a sha256 fingerprint
  prefix + the last 4 characters
- They never read secrets from command-line arguments (which would be
  visible in `ps`) — only from stdin with `read -rs` (echo off)
- For services that call external APIs directly (no fallback), they include
  a **pre-flight test** against the API with the new credential before
  writing to disk
