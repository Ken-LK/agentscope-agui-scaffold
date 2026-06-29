# Security Policy

## Reporting a Vulnerability

Please report security issues privately instead of opening a public issue.

Contact: liukailk.ken@gmail.com

Include:

- A concise description of the issue.
- Reproduction steps or a minimal proof of concept.
- Affected versions or commits.
- Whether credentials, user data, or remote execution are involved.

## Secrets

Do not commit API keys, `.env` files, Redis URLs with passwords, SLS access keys,
or production logs. Use `.env.example` files and environment variables for local
configuration.
