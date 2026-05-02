#!/usr/bin/env bash
# ===============================================================================
# Einmaliges Setup auf dem VPS — legt Bare-Repo + post-receive-Hook an
#
# Annahmen (siehe DEPLOYMENT.md):
#   - Working-Tree liegt unter /var/www/bewerbungen und ist bereits eingerichtet
#     (venv, .env, alembic, systemd-Unit `bewerbungen.service`)
#   - Du hast root- oder sudo-Rechte
#
# Anpassbar via Env-Vars (vor dem Aufruf setzen):
#   BARE_REPO_DIR=/srv/git/bewerbungen.git
#   WORK_TREE=/var/www/bewerbungen
#   SERVICE_NAME=bewerbungen.service
#   DEPLOY_LOG=/var/log/bewerbungen/deploy.log
#
# Aufruf (auf dem VPS):
#   sudo bash setup-bare-repo.sh
# ===============================================================================
set -euo pipefail

BARE_REPO_DIR="${BARE_REPO_DIR:-/srv/git/bewerbungen.git}"
WORK_TREE="${WORK_TREE:-/var/www/bewerbungen}"
SERVICE_NAME="${SERVICE_NAME:-bewerbungen.service}"
DEPLOY_LOG="${DEPLOY_LOG:-/var/log/bewerbungen/deploy.log}"

if [[ $EUID -ne 0 ]]; then
    echo "❌ Bitte mit sudo/root ausführen." >&2
    exit 1
fi

if [[ ! -d "$WORK_TREE" ]]; then
    echo "❌ Working-Tree $WORK_TREE existiert nicht. Bitte erst DEPLOYMENT.md durchgehen." >&2
    exit 1
fi

echo "→ Erstelle Bare-Repo unter $BARE_REPO_DIR"
mkdir -p "$BARE_REPO_DIR"
git init --bare "$BARE_REPO_DIR"

echo "→ Schreibe post-receive Hook"
HOOK_SRC="$(dirname "$0")/post-receive"
if [[ ! -f "$HOOK_SRC" ]]; then
    echo "❌ post-receive nicht gefunden neben dem Setup-Skript" >&2
    exit 1
fi

# Hook installieren und Variablen einsetzen
sed \
    -e "s|@@WORK_TREE@@|$WORK_TREE|g" \
    -e "s|@@BARE_REPO_DIR@@|$BARE_REPO_DIR|g" \
    -e "s|@@SERVICE_NAME@@|$SERVICE_NAME|g" \
    -e "s|@@DEPLOY_LOG@@|$DEPLOY_LOG|g" \
    "$HOOK_SRC" > "$BARE_REPO_DIR/hooks/post-receive"
chmod +x "$BARE_REPO_DIR/hooks/post-receive"

echo "→ Stelle sicher, dass $WORK_TREE ein git-checkout ist (für saubere Resets)"
if [[ ! -d "$WORK_TREE/.git" ]]; then
    cat <<EOF
⚠ $WORK_TREE ist aktuell KEIN git-Working-Tree (kein .git/-Ordner).
  post-receive nutzt 'git --work-tree=$WORK_TREE --git-dir=$BARE_REPO_DIR checkout -f',
  das funktioniert auch ohne lokales .git/ — ist sogar sauberer (keine doppelten DBs).
  Falls du das willst, brauchst du jetzt nichts zu tun.
EOF
fi

echo "→ Logverzeichnis vorbereiten"
mkdir -p "$(dirname "$DEPLOY_LOG")"
touch "$DEPLOY_LOG"

cat <<EOF

✅ Setup fertig.

Lokal auf deinem Mac (im Repo):

    git remote add vps ssh://root@bewerbungen.wolfinisoftware.de$BARE_REPO_DIR
    git push vps master

Beim ersten Push wird automatisch ausgecheckt + Service neu gestartet.
Logs: tail -f $DEPLOY_LOG
EOF
