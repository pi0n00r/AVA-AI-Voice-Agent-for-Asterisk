#!/usr/bin/env bash
# AI-NOTICE:Schema-Version=0.1
# AI-NOTICE:License=AGPL-3.0-or-later
# AI-NOTICE:Project=Ava
# AI-NOTICE:Repository=https://github.com/pi0n00r/AVA-AI-Voice-Agent-for-Asterisk
# AI-NOTICE:Author=Gary Bajaj
set -euo pipefail
umask 0022

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT"

profile=${1:-}
case "$profile" in
  "") ;;
  starter|external-pbx) ;;
  *) echo "usage: $0 [starter|external-pbx]" >&2; exit 2 ;;
esac

need() { command -v "$1" >/dev/null 2>&1 || { echo "missing required command: $1" >&2; exit 1; }; }
need docker
need openssl
docker compose version >/dev/null

if [ ! -f .env ]; then
  cp .env.example .env
  chmod 0600 .env
fi

python_bin=
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then python_bin=$candidate; break; fi
done
[ -n "$python_bin" ] || { echo "python3 is required for safe .env updates" >&2; exit 1; }

env_set() {
  "$python_bin" - "$1" "$2" <<'PY'
import os, pathlib, sys, tempfile
path = pathlib.Path('.env')
key, value = sys.argv[1:]
lines = path.read_text(encoding='utf-8').splitlines()
out, found = [], False
for line in lines:
    if line.startswith(key + '='):
        out.append(f'{key}={value}')
        found = True
    else:
        out.append(line)
if not found:
    out.append(f'{key}={value}')
fd, temp = tempfile.mkstemp(prefix='.env.', dir='.')
try:
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as handle:
        handle.write('\n'.join(out) + '\n')
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)
finally:
    if os.path.exists(temp):
        os.unlink(temp)
PY
}

env_get() {
  "$python_bin" - "$1" <<'PY'
import pathlib, sys
key = sys.argv[1]
for line in pathlib.Path('.env').read_text(encoding='utf-8').splitlines():
    if line.startswith(key + '='):
        print(line.split('=', 1)[1])
        break
PY
}

generate_if_placeholder() {
  key=$1
  value=$(env_get "$key")
  if [ -z "$value" ] || [ "$value" = GENERATED ]; then
    env_set "$key" "$(openssl rand -hex 32)"
  fi
}

generate_if_placeholder JWT_SECRET
generate_if_placeholder LOCAL_WS_AUTH_TOKEN
generate_if_placeholder ASTERISK_ARI_PASSWORD
generate_if_placeholder AVA_SIP_PASSWORD

if [ -n "$profile" ]; then env_set COMPOSE_PROFILES "$profile"; fi
profile=$(env_get COMPOSE_PROFILES)
[ "$profile" = starter ] || [ "$profile" = external-pbx ] || {
  echo "COMPOSE_PROFILES must be starter or external-pbx" >&2
  exit 1
}

env_set HOST_PROJECT_ROOT "$ROOT"
if [ -S /var/run/docker.sock ]; then
  env_set DOCKER_GID "$(stat -c '%g' /var/run/docker.sock)"
fi
if [ "$profile" = starter ]; then env_set ASTERISK_HOST starter_asterisk; fi

mkdir -p config models data logs asterisk_media
if [ ! -f config/ai-agent.yaml ]; then
  cp defaults/ai-agent.yaml config/ai-agent.yaml
fi
chmod 0755 config models data logs asterisk_media
chmod 0644 config/ai-agent.yaml
chmod 0600 .env

if [ ! -f models/llm/qwen2.5-1.5b-instruct-q4_k_m.gguf ]; then
  echo "Downloading the starter speech and language models (one time)..."
  if [ -x "$ROOT/scripts/model_setup.sh" ]; then
    model_setup="$ROOT/scripts/model_setup.sh"
  elif [ -x "$ROOT/../../scripts/model_setup.sh" ]; then
    model_setup="$ROOT/../../scripts/model_setup.sh"
  else
    echo "missing bundled model setup script" >&2
    exit 1
  fi
  AVA_MODELS_DIR="$ROOT/models" "$model_setup" \
    --tier LIGHT --assume-yes --language en-US
fi

docker compose -f compose.yaml config --quiet
docker compose -f compose.yaml pull
docker compose -f compose.yaml up -d --remove-orphans
docker compose -f compose.yaml ps

echo
echo "Ava WebUI: http://localhost:$(env_get AVA_ADMIN_PORT)"
echo "First login: user admin; read config/.first-run-password locally for the one-time password."
if [ "$profile" = starter ]; then
  echo "Starter PBX: register SIP user $(env_get AVA_SIP_USERNAME) and call extension $(env_get AVA_AGENT_EXTENSION)."
fi
