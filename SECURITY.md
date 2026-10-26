# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| master  | :white_check_mark: |

## Reporting a Vulnerability

Please report security vulnerabilities to **Harald Weiss** via one of the following channels:

- **GitHub private vulnerability reporting** (when enabled): Use "Report a vulnerability" under this repository's "Security" tab. Otherwise, use the email address below.
- **Email**: opensource@wolfinisoftware.de

### What to include

- A clear description of the vulnerability
- Steps to reproduce (including required environment variables)
- The affected component(s) (backend, frontend, IMAP proxy, etc.)
- Potential impact (data exposure, authentication bypass, etc.)
- Suggested fix or mitigation (if known)

### Response timeline

- **Acknowledgment**: Within 3 business days
- **Initial assessment**: Within 7 business days
- **Fix / patch**: Depends on severity; you will be kept informed of progress

## Security best practices for contributors

- All commits must be signed off (`git commit -s`) per the Developer Certificate of Origin (DCO).
- Do not commit `.env`, `*.pem`, `config.json`, or database files (`*.db`, `bewerbungstracker.db`). These are already in `.gitignore`.
- Envelope encryption is used: per-user DEK + KEK derived from the user password. Never log encryption keys.
- Never log passwords, encryption keys, JWTs, or refresh tokens.
- IMAP proxy runs on localhost (port 8765) only.
- Dependency updates are managed via Dependabot (see `.github/dependabot.yml`).

## Disclosure policy

We follow coordinated disclosure. Please do not publicly disclose a vulnerability until we have had a reasonable window to investigate and release a fix. Credit will be given upon request.
