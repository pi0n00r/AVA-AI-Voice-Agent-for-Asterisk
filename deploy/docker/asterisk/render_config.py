#!/usr/bin/env python3
# AI-NOTICE:Schema-Version=0.1
# AI-NOTICE:License=AGPL-3.0-or-later
# AI-NOTICE:Project=Ava
# AI-NOTICE:Repository=https://github.com/pi0n00r/AVA-AI-Voice-Agent-for-Asterisk
# AI-NOTICE:Author=Gary Bajaj
import os
import pathlib
import re

ROOT = pathlib.Path(os.getenv("ASTERISK_CONFIG_DIR", "/etc/asterisk"))
SAFE = re.compile(r"^[A-Za-z0-9_.!@%+=,:/-]{1,128}$")


def value(name: str, default: str = "") -> str:
    result = os.getenv(name, default).strip()
    if not SAFE.fullmatch(result):
        raise SystemExit(f"invalid {name}")
    return result


ari_user = value("ASTERISK_ARI_USERNAME", "ava")
ari_password = value("ASTERISK_ARI_PASSWORD")
sip_user = value("AVA_SIP_USERNAME", "7001")
sip_password = value("AVA_SIP_PASSWORD")
sip_extension = value("AVA_SIP_EXTENSION", "7001")
agent_extension = value("AVA_AGENT_EXTENSION", "700")
if not ari_password or not sip_password:
    raise SystemExit("ARI and SIP passwords are required")

files = {
    "http.conf": """[general]\nenabled=yes\nbindaddr=::\nbindport=8088\n""",
    "ari.conf": f"""[general]\nenabled=yes\npretty=no\nallowed_origins=*\n\n[{ari_user}]\ntype=user\nread_only=no\npassword={ari_password}\n""",
    "rtp.conf": """[general]\nrtpstart=10000\nrtpend=10019\nicesupport=no\n""",
    "pjsip.conf": f"""[global]\ntype=global\nuser_agent=Ava Starter PBX\n\n[transport-udp]\ntype=transport\nprotocol=udp\nbind=[::]:5060\n\n[{sip_user}]\ntype=endpoint\ntransport=transport-udp\ncontext=ava-starter\ndisallow=all\nallow=ulaw\nauth={sip_user}-auth\naors={sip_user}\ndirect_media=no\n\n[{sip_user}-auth]\ntype=auth\nauth_type=userpass\nusername={sip_user}\npassword={sip_password}\n\n[{sip_user}]\ntype=aor\nmax_contacts=1\nremove_existing=yes\n""",
    "extensions.conf": f"""[general]\nstatic=yes\nwriteprotect=yes\n\n[ava-starter]\nexten => {agent_extension},1,NoOp(Ava starter call)\n same => n,Answer()\n same => n,Stasis(asterisk-ai-voice-agent)\n same => n,Hangup()\n\nexten => {sip_extension},1,Dial(PJSIP/{sip_user},30)\n same => n,Hangup()\n""",
    "modules.conf": """[modules]\nautoload=yes\n""",
    "logger.conf": """[general]\ndateformat=%F %T\n\n[logfiles]\nconsole => notice,warning,error\n""",
}

ROOT.mkdir(parents=True, exist_ok=True)
for name, content in files.items():
    path = ROOT / name
    path.write_text(content, encoding="utf-8")
    path.chmod(0o640)
