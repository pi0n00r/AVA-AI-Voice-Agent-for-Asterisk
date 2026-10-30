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

### Public container packages

The maintained images are publicly readable without a GitHub account:

- [`ava-ai-engine`](https://github.com/pi0n00r/AVA-AI-Voice-Agent-for-Asterisk/pkgs/container/ava-ai-engine)
- [`ava-admin-ui`](https://github.com/pi0n00r/AVA-AI-Voice-Agent-for-Asterisk/pkgs/container/ava-admin-ui)
- [`ava-local-ai`](https://github.com/pi0n00r/AVA-AI-Voice-Agent-for-Asterisk/pkgs/container/ava-local-ai)
- [`ava-starter-asterisk`](https://github.com/pi0n00r/AVA-AI-Voice-Agent-for-Asterisk/pkgs/container/ava-starter-asterisk)

GitHub may hide package discovery controls from signed-out visitors; these direct links and anonymous GHCR pulls remain supported.

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

## OpenAI-compatible transcription

The Admin API can expose the configured local STT provider through:

- `GET /v1/models`
- `POST /v1/audio/transcriptions`

Set `AAVA_SPEECH_API_KEY` for Bearer authentication, or set both
`AAVA_SPEECH_API_USERNAME` and `AAVA_SPEECH_API_PASSWORD` for Basic
authentication in the Admin backend environment. The endpoints fail closed when
neither credential is set. Recreate the Admin container after changing these
environment variables; browser login credentials are unrelated. If the local
AI WebSocket requires `LOCAL_WS_AUTH_TOKEN`, configure the same token for the
Admin backend. The Admin UI itself has no transcription screen.
The transcription route accepts the standard multipart `file`, `model`,
`language`, and `response_format` fields; use model `whisper-1`. For example,
`curl -u stt-client -F 'file=@sample.wav' -F 'model=whisper-1' https://YOUR-ADMIN-HOST/v1/audio/transcriptions`
prompts for the Basic password without placing it on the command line.
Supported response formats are `json`, `text`, `verbose_json`, `srt`, and
`vtt`. The last three use one whole-file segment and synthetic 0-to-duration
timing, not model-derived word or segment timestamps.

The facade accepts FFmpeg-decodable audio such as WAV, MP3, M4A, OGG and WebM,
with a 25 MiB file cap, 25 MiB + 64 KiB total multipart cap, and 120-second
decoded-audio cap. Upload receipt times out after 30 seconds and decoding after
90 seconds. The local AI service runs at most one batch job in a killable
separate process, with no waiting queue and a 180-second worker deadline. A
live-call session rejects new batch work and preempts a running batch.
Disconnection or timeout cancels the worker; a lost HTTP response is not
evidence of a transcript. The Admin wait defaults to 240 seconds
(`AAVA_SPEECH_STT_TIMEOUT_SECONDS`, clamped to 10-600). A shorter API timeout
cancels its WebSocket request and reaps the isolated batch worker.

Batch transcription uses the configured local Vosk, Faster-Whisper or
Whisper.cpp backend; unsupported or unloaded backends fail explicitly, with no
cloud fallback. Only Faster-Whisper honors a per-request two-letter language
code or `auto` detection; English-only `.en` models accept `en` only. Omit
`language` for Vosk and Whisper.cpp so their configured model language is used.
Keep the Admin API behind the same network controls used for the rest of the
operator surface and keep its speech credential distinct from browser login.

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
