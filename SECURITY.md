# Security policy

## Supported source

Security maintenance applies to the current `bajaj/maintained` branch on a
best-effort basis. Historical tags, archives, deployment kits, and downstream
installations are not separate supported release trains. This public repository
does not operate a hosted Ava service.

## Report a vulnerability

Use GitHub's private vulnerability-reporting form for this repository:

https://github.com/pi0n00r/AVA-AI-Voice-Agent-for-Asterisk/security/advisories/new

Do not disclose an unpatched vulnerability in a public issue, discussion, pull
request, call recording, or log attachment. Include only the minimum material
needed to reproduce the problem:

- affected commit or component;
- impact and preconditions;
- reproduction steps or a minimal proof of concept;
- suggested remediation, when known.

Remove credentials, caller data, recordings, private prompts, internal hostnames,
and infrastructure topology. If a report concerns upstream code, the maintainer
may coordinate it with the upstream project without disclosing unrelated private
deployment information.

Reports are assessed and corrected on a best-effort basis. This fork makes no
fixed acknowledgment, remediation, support, or disclosure-timeline commitment.

## Security expectations

- Keep secrets outside source control and generated artifacts.
- Restrict management, Asterisk, media, MCP, and provider endpoints to their
  intended trust boundaries.
- Use least-privilege credentials and encrypted transport.
- Treat call audio, transcripts, DTMF, prompts, and tool results as sensitive.
- Keep dependency and container updates reviewable and reproducible.
- Preserve redaction, metadata-only audit, and fail-closed authorization paths.
- Do not publish private Compose overlays, environment files, databases, models,
  recordings, or operator recovery material.

The repository's public source is only one part of deployment security. Operators
remain responsible for Asterisk, reverse proxy, network, host, provider, and data
retention controls in their own environment.
