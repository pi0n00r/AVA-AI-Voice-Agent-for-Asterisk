# AI-NOTICE:Schema-Version=0.1
# AI-NOTICE:License=AGPL-3.0-or-later
# AI-NOTICE:Project=Ava
# AI-NOTICE:Repository=https://github.com/pi0n00r/AVA-AI-Voice-Agent-for-Asterisk
# AI-NOTICE:Author=Gary Bajaj
FROM docker.io/library/ubuntu:24.04@sha256:534baea6a22c03a63003dbc8dbe78fe34bc0d7e595d9a9dc9834884ff530eb55

RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends asterisk python3-minimal \
 && rm -rf /var/lib/apt/lists/*

COPY deploy/docker/asterisk/render_config.py /usr/local/lib/ava/render_config.py
COPY deploy/docker/asterisk/entrypoint.sh /usr/local/bin/ava-asterisk-entrypoint
RUN chmod 0755 /usr/local/bin/ava-asterisk-entrypoint

EXPOSE 5060/udp 8088 10000-10019/udp
ENTRYPOINT ["/usr/local/bin/ava-asterisk-entrypoint"]
