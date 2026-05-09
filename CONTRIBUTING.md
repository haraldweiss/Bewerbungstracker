# Mitwirken an Bewerbungstracker

Vielen Dank für dein Interesse am Projekt! Beiträge in Form von Pull-Requests,
Bug-Reports oder Vorschlägen sind ausdrücklich willkommen.

## Lizenz und Urheberrecht

Bewerbungstracker steht unter der [GNU AGPL v3.0](LICENSE). Alle Beiträge werden
**unter derselben Lizenz** in das Projekt aufgenommen. Du behältst das
Urheberrecht an deinem Beitrag, lizenzierst ihn aber so, dass er Teil von
Bewerbungstracker werden kann.

## Developer Certificate of Origin (DCO)

Statt eines formellen Contributor-License-Agreements nutzt das Projekt das
[Developer Certificate of Origin v1.1](https://developercertificate.org/).
Mit jedem Commit bestätigst du Folgendes:

> By making a contribution to this project, I certify that:
>
> (a) The contribution was created in whole or in part by me and I have the
>     right to submit it under the open source license indicated in the file; or
>
> (b) The contribution is based upon previous work that, to the best of my
>     knowledge, is covered under an appropriate open source license and I have
>     the right under that license to submit that work with modifications,
>     whether created in whole or in part by me, under the same open source
>     license (unless I am permitted to submit under a different license), as
>     indicated in the file; or
>
> (c) The contribution was provided directly to me by some other person who
>     certified (a), (b) or (c) and I have not modified it.
>
> (d) I understand and agree that this project and the contribution are public
>     and that a record of the contribution (including all personal information
>     I submit with it, including my sign-off) is maintained indefinitely and
>     may be redistributed consistent with this project or the open source
>     license(s) involved.

### Sign-off auf jedem Commit

Damit dein Commit das DCO bestätigt, muss er einen `Signed-off-by:`-Trailer
mit deinem echten Namen und einer erreichbaren E-Mail enthalten. Git macht
das automatisch mit:

```bash
git commit -s -m "Eine kurze, präzise Commit-Beschreibung"
```

Falls du das Sign-off in einem bestehenden Commit vergessen hast:

```bash
git commit --amend -s --no-edit          # nur den letzten Commit
git rebase HEAD~N --signoff               # die letzten N Commits
```

## Pull-Request-Workflow

1. Forke das Repository auf GitHub.
2. Erstelle einen feature-Branch (`git checkout -b feat/kurze-beschreibung`).
3. Implementiere die Änderung. Halte dich an den vorhandenen Codestil.
4. Commits sauber halten und mit `-s` signieren.
5. PR gegen die Default-Branch öffnen mit kurzer Beschreibung des "Was" und "Warum".

## Bug-Reports

Bitte ein GitHub-Issue mit Schritten zur Reproduktion, erwartetem vs.
tatsächlichem Verhalten, Umgebung, und relevanten Logs.

## Sicherheitsmeldungen

Sicherheitsrelevante Probleme bitte **nicht** als öffentliches Issue, sondern
direkt per E-Mail an den Maintainer (Adresse aus dem Repo-Profil).
