# Contributing to the maintained Ava fork

This repository is a source-only maintained fork of
`hkjarral/AVA-AI-Voice-Agent-for-Asterisk`. It does not provide hosted Ava
services, consulting, demonstrations, sponsorship, or a public support
community.

## Scope

Useful contributions are narrowly focused on the maintained source:

- correctness and reliability fixes;
- security and privacy hardening;
- Asterisk, AudioSocket, speech-provider, and MCP interoperability;
- dual-stack networking and reproducible deployment behavior;
- regression tests and accurate operator documentation.

General support requests and deployment-specific private configuration do not
belong in the public repository. Do not submit credentials, recordings, call
content, private prompts, environment files, or infrastructure details.

## Workflow

1. Fork `pi0n00r/AVA-AI-Voice-Agent-for-Asterisk`.
2. Branch from `bajaj/maintained`.
3. Keep the change bounded and preserve upstream attribution.
4. Add focused regression coverage for behavioral changes.
5. Run the relevant tests and formatting checks.
6. Open a pull request against `bajaj/maintained` with the problem, approach,
   verification, and compatibility impact.

Pull requests are reviewed on a best-effort basis. There is no guaranteed
response or merge timetable. Security vulnerabilities must use the private
reporting route in [SECURITY.md](SECURITY.md), not a public pull request.

## Licensing and notices

Contributions to upstream-derived files remain under the repository's MIT
license unless the file says otherwise. Fleet-authored components carrying an
`AI-NOTICE` or another explicit header retain the license named there, including
AGPL-3.0-or-later where applicable. Do not remove copyright, attribution,
Contributor Covenant, provenance, or machine-readable notice headers.

By submitting a contribution, you represent that you have the right to provide
it under the applicable file and repository licenses.
