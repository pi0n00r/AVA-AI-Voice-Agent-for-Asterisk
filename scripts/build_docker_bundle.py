#!/usr/bin/env python3
# AI-NOTICE:Schema-Version=0.1
# AI-NOTICE:License=AGPL-3.0-or-later
# AI-NOTICE:Project=Ava
# AI-NOTICE:Repository=https://github.com/pi0n00r/AVA-AI-Voice-Agent-for-Asterisk
# AI-NOTICE:Author=Gary Bajaj
"""Build a deterministic, self-contained Ava Docker installer archive."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
from pathlib import Path
import tarfile


ROOT = Path(__file__).resolve().parents[1]
DOCKER_SOURCE = ROOT / "deploy" / "docker"
EXCLUDED_PARTS = {"__pycache__", "config", "models", "data", "logs", "asterisk_media"}
LEGAL_FILES = (
    "LICENSE",
    "LICENSE-AGPL-3.0.txt",
    "BAJAJ-FLEET-NOTICE.md",
    "UPSTREAM-LINEAGE.md",
)


def mode_for(path: str) -> int:
    name = path.rsplit("/", 1)[-1]
    if name == ".env.example":
        return 0o600
    if name in {"install.sh", "entrypoint.sh", "render_config.py", "model_setup.sh"}:
        return 0o755
    return 0o644


def source_files() -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for source in sorted(DOCKER_SOURCE.rglob("*")):
        relative = source.relative_to(DOCKER_SOURCE)
        if not source.is_file() or any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        files[relative.as_posix()] = source.read_bytes()
    files["scripts/model_setup.sh"] = (ROOT / "scripts" / "model_setup.sh").read_bytes()
    for name in LEGAL_FILES:
        files[name] = (ROOT / name).read_bytes()
    return files


def add_member(archive: tarfile.TarFile, name: str, content: bytes, mode: int) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(content)
    info.mode = mode
    info.mtime = 0
    info.uid = info.gid = 0
    info.uname = info.gname = "root"
    archive.addfile(info, io.BytesIO(content))


def build(version: str, source_ref: str, output: Path) -> tuple[Path, str]:
    package_root = f"ava-docker-{version}"
    files = source_files()
    env_example = files[".env.example"].decode("utf-8")
    files[".env.example"] = env_example.replace(
        "AVA_IMAGE_TAG=maintained", f"AVA_IMAGE_TAG=sha-{source_ref}"
    ).encode()
    files["SOURCE.txt"] = (
        "Repository: https://github.com/pi0n00r/AVA-AI-Voice-Agent-for-Asterisk\n"
        f"Source: {source_ref}\n"
        f"Package: {version}\n"
    ).encode()
    manifest = "".join(
        f"{hashlib.sha256(content).hexdigest()}  {name}\n"
        for name, content in sorted(files.items())
    ).encode()
    files["PACKAGE-MANIFEST.sha256"] = manifest

    output.mkdir(parents=True, exist_ok=True)
    archive_path = output / f"{package_root}.tar.gz"
    with archive_path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as archive:
                root_info = tarfile.TarInfo(package_root)
                root_info.type = tarfile.DIRTYPE
                root_info.mode = 0o755
                root_info.mtime = 0
                root_info.uid = root_info.gid = 0
                root_info.uname = root_info.gname = "root"
                archive.addfile(root_info)
                for name, content in sorted(files.items()):
                    add_member(archive, f"{package_root}/{name}", content, mode_for(name))

    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    checksum_path = archive_path.with_suffix(archive_path.suffix + ".sha256")
    checksum_path.write_text(f"{digest}  {archive_path.name}\n", encoding="ascii")
    return archive_path, digest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-ref", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    archive, digest = build(args.version, args.source_ref, args.output)
    print(f"{digest}  {archive}")


if __name__ == "__main__":
    main()
