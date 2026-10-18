<!--
AI-NOTICE:Schema-Version=0.1
AI-NOTICE:License=AGPL-3.0-or-later
AI-NOTICE:Project=Ava
AI-NOTICE:Repository=https://github.com/pi0n00r/AVA-AI-Voice-Agent-for-Asterisk
AI-NOTICE:Scope=Fleet-authored fork notice; retained upstream source remains MIT
-->

# Ava for Asterisk

This is an independent maintained fork of
[AVA AI Voice Agent for Asterisk](https://github.com/hkjarral/AVA-AI-Voice-Agent-for-Asterisk).
It does not provide hosting, commercial services, managed deployment, a public
demo, or a support program.

## No fundraising

This fork does not solicit or accept donations. Any fundraising links, prompts,
or payment destinations inherited from upstream are not operated, endorsed, or
accepted by this fork or its maintainers. They remain source artifacts pending
removal from the maintained runtime during the next upstream integration.

If you wish to support the original project, verify the recipient independently
through the upstream repository. No contribution made elsewhere funds this fork.

## Maintained scope

The fork retains upstream's voice-agent application and operator UI while
maintaining these qualified areas:

- Asterisk ARI and AudioSocket call handling.
- Modular and full-agent speech-provider paths.
- Local AI support, including Faster-Whisper utterance finalization and
  response-task handling.
- Streamable HTTP MCP transport using the official MCP SDK, alongside stdio.
- Configuration, authentication, privacy, dual-stack, and deployment hardening.
- DTMF log redaction without changing native digit delivery to call handlers.

Not every inherited provider, optional integration, sample, or UI path is
qualified by the maintainers. Validate the intended provider and call path
before deployment.

## Docker quick start

The supported public package has two profiles built from the same images:

- `starter` includes a sandbox Asterisk server, WebUI, voice engine, and local
  speech stack for evaluation and customization.
- `external-pbx` connects that same WebUI and engine to an existing Asterisk or
  FreePBX server over ARI and AudioSocket.

Operators configure `.env`; the package supplies versioned safe defaults and
generates the remaining runtime files. Start with:

```bash
cd deploy/docker
cp .env.example .env
./install.sh starter
```

Open `http://HOST:3003`. For an existing PBX, set its ARI connection in `.env`
and run `./install.sh external-pbx`. See
[`deploy/docker/README.md`](deploy/docker/README.md) for the exact boundary,
first-login process, and upgrade commands.

## Deployment boundary

This repository contains source, tests, public documentation, and a generic
Docker package. Credentials, live configuration, recordings, downloaded models,
databases, and private deployment assembly remain excluded. The package starts
a new generic installation; it does not reproduce any private installation.

The maintained branch is `bajaj/maintained`. Review [`CHANGELOG.md`](CHANGELOG.md),
[`DEPLOY.md`](DEPLOY.md), and [`SECURITY.md`](SECURITY.md) before use. Upgrades
should be tested and reversible.

## Security and privacy

- Do not commit `.env`, provider credentials, caller data, recordings, or live
  configuration.
- Treat DTMF as sensitive authentication material and keep it out of logs.
- Treat timed-out call or tool operations as having an unknown outcome until
  reconciled; do not replay them blindly.
- Protect operator interfaces with deployment-specific authentication and
  network controls.
- Validate both IPv4 and IPv6 behavior where a listener is enabled.

Please use the process in [`SECURITY.md`](SECURITY.md) for vulnerabilities in
this fork. Upstream-only issues belong with the upstream project.

## Upstream and contributions

The original AVA project and its contributors remain credited in
[`CONTRIBUTORS.md`](CONTRIBUTORS.md) and the Git history. This fork is not
associated with, endorsed by, sponsored by, or officially affiliated with the
upstream project or its authors.

Changes to this fork should target `bajaj/maintained`, preserve attribution,
include focused regression coverage, and exclude private deployment material.

## License

The inherited upstream source remains under its MIT license. Fleet-authored
additions are licensed under AGPL-3.0-or-later as described in
[`BAJAJ-FLEET-NOTICE.md`](BAJAJ-FLEET-NOTICE.md). No change here removes or
replaces genuine contributor or third-party notices.
