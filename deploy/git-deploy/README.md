# Git-basierter Deploy auf den VPS

Ergänzt das bisherige `scp`-Pattern um einen Bare-Repo + post-receive-Hook,
sodass `git push vps master` automatisch deployt:

1. atomarer Checkout in `/var/www/bewerbungen`
2. `pip install -r requirements.txt` falls geändert
3. `alembic upgrade head` falls neue Migration
4. `systemctl restart bewerbungen.service`
5. Smoke-Check: ist der Service nach 2s active?

Logs: `/var/log/bewerbungen/deploy.log`. Lock: `/var/lock/bewerbungen-deploy.lock`.

## Einmaliges Setup

### 1) Skripte auf den VPS übertragen

```bash
# Lokal:
cd /Library/WebServer/Documents/Bewerbungstracker
scp deploy/git-deploy/setup-bare-repo.sh deploy/git-deploy/post-receive \
    root@bewerbungen.wolfinisoftware.de:/root/
```

### 2) Setup auf dem VPS ausführen

```bash
ssh root@bewerbungen.wolfinisoftware.de
cd /root
chmod +x setup-bare-repo.sh
./setup-bare-repo.sh
# → erstellt /srv/git/bewerbungen.git und installiert den Hook
```

Optional vorher Variablen setzen, falls Standard-Pfade nicht passen:

```bash
BARE_REPO_DIR=/srv/git/bewerbungen.git \
WORK_TREE=/var/www/bewerbungen \
SERVICE_NAME=bewerbungen.service \
./setup-bare-repo.sh
```

### 3) Lokal das Remote eintragen

```bash
# Im Repo auf dem Mac:
git remote add vps ssh://root@bewerbungen.wolfinisoftware.de/srv/git/bewerbungen.git

# Erster Deploy:
git push vps master
```

Beim Push siehst du im Terminal die Deploy-Logs (kommen direkt vom Hook).

## Daily Use

```bash
# Code ändern, committen, pushen → fertig
git push vps master
```

Wenn du parallel auch zu GitHub pushen willst:

```bash
git push origin master   # Code-Repo
git push vps master      # Live-Deploy
```

Oder beides in einem:

```bash
git remote set-url --add --push vps ssh://root@bewerbungen.wolfinisoftware.de/srv/git/bewerbungen.git
git remote set-url --add --push vps git@github.com:dein-user/dein-repo.git
git push vps master
```

## Rollback

Wenn ein Deploy etwas kaputt macht:

```bash
ssh root@bewerbungen.wolfinisoftware.de
git --work-tree=/var/www/bewerbungen --git-dir=/srv/git/bewerbungen.git log --oneline -10
git --work-tree=/var/www/bewerbungen --git-dir=/srv/git/bewerbungen.git checkout -f <hash>
systemctl restart bewerbungen.service
```

Oder lokal:

```bash
# Vorletzten Commit mit force-push deployen (keine GitHub-History beeinflussen!)
git push vps <hash>:master --force
```

⚠ `--force` betrifft nur das `vps`-Remote, nicht GitHub. Trotzdem mit Bedacht.

## scp parallel weiter nutzen

Bare-Repo + scp schließen sich nicht aus. Für 1-File-Hotfixes ohne Commit:

```bash
scp index.html root@bewerbungen.wolfinisoftware.de:/var/www/bewerbungen/
```

Caveat: nächster `git push vps` setzt das wieder auf den letzten Commit-Stand
zurück (`git checkout -f` ist destruktiv im Working-Tree). Wenn der Hotfix
bleiben soll, also danach committen + pushen.

## Was der Hook NICHT macht

- **Keine static-build-Schritte** (npm, webpack) — wenn die später dazukommen,
  in `post-receive` ergänzen.
- **Kein Restart von `imap-proxy` / `email-service`** — die laufen aktuell
  auf dem Mac (Hybrid-Setup), nicht auf dem VPS. Bei Migration auf VPS-only
  einfach in `post-receive` zwei `systemctl restart`-Zeilen ergänzen.
- **Kein DB-Backup vor Migration** — der `bewerbungen-backup.timer` läuft
  täglich. Bei riskanten Migrations vorher manuell triggern:
  `systemctl start bewerbungen-backup.service`.
