from pathlib import Path
import hashlib
import os
import shutil
import subprocess
import tarfile

import yaml


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "deploy" / "docker"


def test_distribution_has_two_profiles_and_no_builds():
    compose = yaml.safe_load((BUNDLE / "compose.yaml").read_text(encoding="utf-8"))
    services = compose["services"]
    assert set(services) == {"ai_engine", "local_ai_server", "admin_ui", "starter_asterisk"}
    assert services["starter_asterisk"]["profiles"] == ["starter"]
    assert all("build" not in service for service in services.values())


def test_every_published_port_is_explicitly_dual_stack():
    compose = yaml.safe_load((BUNDLE / "compose.yaml").read_text(encoding="utf-8"))
    for service in compose["services"].values():
        ports = service.get("ports", [])
        assert len(ports) % 2 == 0
        for index in range(0, len(ports), 2):
            assert str(ports[index]).startswith("${AVA_BIND_IPV4")
            assert str(ports[index + 1]).startswith("[${AVA_BIND_IPV6")


def test_operator_configuration_is_env_only():
    readme = (BUNDLE / "README.md").read_text(encoding="utf-8")
    assert "configure `.env`" in readme
    assert "edit config/ai-agent.yaml" not in readme
    assert (BUNDLE / ".env.example").is_file()
    assert (BUNDLE / "defaults" / "ai-agent.yaml").is_file()


def test_admin_image_contains_shared_runtime_package():
    dockerfile = (ROOT / "admin_ui" / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY src/ ./src/" in dockerfile
    assert "COPY src/config_apply.py ./config_apply.py" not in dockerfile


def test_starter_dialplan_enters_stasis_without_audiosocket_duplication():
    source = (BUNDLE / "asterisk" / "render_config.py").read_text(encoding="utf-8")
    assert "Stasis(asterisk-ai-voice-agent)" in source
    assert "AudioSocket(" not in source
    assert r"bind=[::]:5060" in source
    assert "bind=0.0.0.0:5060" not in source


def test_starter_config_renderer_keeps_secrets_out_of_process_output(tmp_path):
    env = {
        **os.environ,
        "ASTERISK_CONFIG_DIR": str(tmp_path),
        "ASTERISK_ARI_USERNAME": "ava",
        "ASTERISK_ARI_PASSWORD": "ari-test-secret",
        "AVA_SIP_USERNAME": "7001",
        "AVA_SIP_PASSWORD": "sip-test-secret",
        "AVA_SIP_EXTENSION": "7001",
        "AVA_AGENT_EXTENSION": "700",
    }
    result = subprocess.run(
        ["python3", str(BUNDLE / "asterisk" / "render_config.py")],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout == result.stderr == ""
    assert "Stasis(asterisk-ai-voice-agent)" in (tmp_path / "extensions.conf").read_text()
    assert "ari-test-secret" in (tmp_path / "ari.conf").read_text()
    assert "sip-test-secret" in (tmp_path / "pjsip.conf").read_text()
    assert all(path.stat().st_mode & 0o777 == 0o640 for path in tmp_path.iterdir())


def test_installer_uses_env_only_and_preserves_existing_config(tmp_path):
    repo = tmp_path / "repo"
    bundle = repo / "deploy" / "docker"
    shutil.copytree(BUNDLE, bundle)
    (repo / "scripts").mkdir(parents=True)
    shutil.copy2(ROOT / "scripts" / "model_setup.sh", repo / "scripts" / "model_setup.sh")
    (bundle / "models" / "llm").mkdir(parents=True)
    (bundle / "models" / "llm" / "qwen2.5-1.5b-instruct-q4_k_m.gguf").write_bytes(b"fixture")
    (bundle / "config").mkdir()
    sentinel = bundle / "config" / "ai-agent.yaml"
    sentinel.write_text("sentinel: keep\n", encoding="utf-8")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker = fake_bin / "docker"
    docker.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    docker.chmod(0o755)
    env = {**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}"}
    subprocess.run(
        [str(bundle / "install.sh"), "external-pbx"],
        cwd=bundle,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    assert sentinel.read_text(encoding="utf-8") == "sentinel: keep\n"
    env_text = (bundle / ".env").read_text(encoding="utf-8")
    assert "COMPOSE_PROFILES=external-pbx" in env_text
    assert "=GENERATED" not in env_text
    assert (bundle / ".env").stat().st_mode & 0o777 == 0o600


def test_standalone_bundle_is_reproducible_complete_and_installable(tmp_path):
    builder = ROOT / "scripts" / "build_docker_bundle.py"
    output = tmp_path / "out"
    command = [
        "python3",
        str(builder),
        "--version",
        "test",
        "--source-ref",
        "fixture-commit",
        "--output",
        str(output),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)
    archive = output / "ava-docker-test.tar.gz"
    first_digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    subprocess.run(command, check=True, capture_output=True, text=True)
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == first_digest

    with tarfile.open(archive, "r:gz") as package:
        names = set(package.getnames())
        assert "ava-docker-test/install.sh" in names
        assert "ava-docker-test/compose.yaml" in names
        assert "ava-docker-test/scripts/model_setup.sh" in names
        assert "ava-docker-test/PACKAGE-MANIFEST.sha256" in names
        assert "ava-docker-test/LICENSE" in names
        assert "ava-docker-test/.env" not in names
        assert package.getmember("ava-docker-test/.env.example").mode == 0o600
        assert package.getmember("ava-docker-test/install.sh").mode == 0o755
        package.extractall(tmp_path / "extract", filter="data")

    extracted = tmp_path / "extract" / "ava-docker-test"
    assert "AVA_IMAGE_TAG=sha-fixture-commit" in (extracted / ".env.example").read_text()
    subprocess.run(
        ["sha256sum", "--check", "PACKAGE-MANIFEST.sha256"],
        cwd=extracted,
        check=True,
        capture_output=True,
        text=True,
    )
    (extracted / "models" / "llm").mkdir(parents=True)
    (extracted / "models" / "llm" / "qwen2.5-1.5b-instruct-q4_k_m.gguf").write_bytes(b"fixture")
    fake_bin = tmp_path / "bin-bundle"
    fake_bin.mkdir()
    docker = fake_bin / "docker"
    docker.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    docker.chmod(0o755)
    env = {**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}"}
    subprocess.run(
        [str(extracted / "install.sh"), "starter"],
        cwd=extracted,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert (extracted / ".env").stat().st_mode & 0o777 == 0o600


def test_documented_light_model_tier_is_accepted_without_network(tmp_path):
    fake_bin = tmp_path / "model-bin"
    fake_bin.mkdir()
    curl = fake_bin / "curl"
    curl.write_text(
        "#!/bin/sh\n"
        "while [ $# -gt 0 ]; do\n"
        "  if [ \"$1\" = -o ]; then shift; mkdir -p \"$(dirname \"$1\")\"; : > \"$1\"; exit 0; fi\n"
        "  shift\n"
        "done\n"
        "exit 2\n",
        encoding="utf-8",
    )
    curl.chmod(0o755)
    unzip = fake_bin / "unzip"
    unzip.write_text(
        "#!/bin/sh\n"
        "while [ $# -gt 0 ]; do\n"
        "  if [ \"$1\" = -d ]; then shift; mkdir -p \"$1\"; : > \"$1/README\"; exit 0; fi\n"
        "  shift\n"
        "done\n"
        "exit 2\n",
        encoding="utf-8",
    )
    unzip.chmod(0o755)
    models = tmp_path / "models"
    env = {
        **os.environ,
        "AVA_MODELS_DIR": str(models),
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
    }
    result = subprocess.run(
        [str(ROOT / "scripts" / "model_setup.sh"), "--tier", "LIGHT", "--assume-yes"],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Selected tier: LIGHT_CPU (override)" in result.stdout
    assert "Models ready" in result.stdout
    assert (models / "llm" / "qwen2.5-1.5b-instruct-q4_k_m.gguf").is_file()
