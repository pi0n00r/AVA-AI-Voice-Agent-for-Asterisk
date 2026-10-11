#!/bin/sh
# AI-NOTICE:Schema-Version=0.1
# AI-NOTICE:License=AGPL-3.0-or-later
# AI-NOTICE:Project=Ava
# AI-NOTICE:Repository=https://github.com/pi0n00r/AVA-AI-Voice-Agent-for-Asterisk
# AI-NOTICE:Author=Gary Bajaj
set -eu
umask 0022
python3 /usr/local/lib/ava/render_config.py
exec /usr/sbin/asterisk -f -vvv
