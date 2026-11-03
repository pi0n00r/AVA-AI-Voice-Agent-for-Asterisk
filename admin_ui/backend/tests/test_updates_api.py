import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest
from fastapi import HTTPException

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from api import system  # noqa: E402


def _jobs_dir(root: Path) -> Path:
    jobs = root / ".agent" / "updates" / "jobs"
    jobs.mkdir(parents=True, exist_ok=True)
    return jobs


def test_configured_update_source_accepts_named_fork_remote(monkeypatch) -> None:
    monkeypatch.setenv("AAVA_UPDATE_REMOTE", "public")
    monkeypatch.setenv("AAVA_UPDATE_DEFAULT_BRANCH", "bajaj/maintained")

    assert system._configured_update_remote() == "public"
    assert system._configured_update_default_branch() == "bajaj/maintained"


@pytest.mark.parametrize("remote", ["-public", "public remote", "../public", "public/@{bad}"])
def test_configured_update_remote_rejects_unsafe_names(monkeypatch, remote: str) -> None:
    monkeypatch.setenv("AAVA_UPDATE_REMOTE", remote)
    with pytest.raises(HTTPException, match="Invalid configured update remote"):
        system._configured_update_remote()


@pytest.mark.asyncio
async def test_updates_plan_uses_one_configured_remote_and_default_branch(monkeypatch, tmp_path) -> None:
    captured: dict = {}

    def fake_run(*_args, **kwargs):
        captured.update(kwargs)
        return 0, '{"dirty": false}'

    async def fake_active_calls():
        return {"active_calls": 0, "reachable": True}

    monkeypatch.setenv("AAVA_UPDATE_REMOTE", "public")
    monkeypatch.setenv("AAVA_UPDATE_DEFAULT_BRANCH", "bajaj/maintained")
    monkeypatch.setattr(system, "_project_host_root_from_admin_ui_container", lambda: str(tmp_path))
    monkeypatch.setattr(system, "_run_updater_ephemeral", fake_run)
    monkeypatch.setattr(system, "_check_active_calls", fake_active_calls)

    response = await system.updates_plan(ref=None)

    assert response.plan["active_calls"] == 0
    assert captured["env"]["AAVA_UPDATE_REMOTE"] == "public"
    assert captured["env"]["AAVA_UPDATE_REF"] == "bajaj/maintained"
    assert captured["prefer_pull_ref"] is None


@pytest.mark.asyncio
async def test_updates_plan_rejects_explicit_empty_ref(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(system, "_project_host_root_from_admin_ui_container", lambda: str(tmp_path))
    with pytest.raises(HTTPException) as exc:
        await system.updates_plan(ref="")
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_updates_run_rejects_explicit_empty_ref(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(system, "_project_host_root_from_admin_ui_container", lambda: str(tmp_path))
    monkeypatch.setattr(system, "_docker_sock_host_path_from_admin_ui_container", lambda: "/var/run/docker.sock")
    with pytest.raises(HTTPException) as exc:
        await system.updates_run(system.UpdateRunRequest(ref=""))
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_updates_branches_uses_configured_remote(monkeypatch, tmp_path) -> None:
    captured: dict = {}

    def fake_run(*_args, **kwargs):
        captured.update(kwargs)
        return 0, "abc123\trefs/heads/bajaj/maintained\n"

    monkeypatch.setenv("AAVA_UPDATE_REMOTE", "public")
    monkeypatch.setattr(system, "_project_host_root_from_admin_ui_container", lambda: str(tmp_path))
    monkeypatch.setattr(system, "_run_updater_ephemeral", fake_run)

    response = await system.updates_branches()

    assert response.branches == ["bajaj/maintained"]
    assert "ls-remote --heads public" in captured["command"]


def test_cli_install_path_validation_accepts_simple_absolute_path() -> None:
    assert system._validate_cli_install_path("/usr/local/bin/agent") == "/usr/local/bin/agent"
    assert system._validate_cli_install_path("  /opt/aava-agent_1.2/bin/agent  ") == "/opt/aava-agent_1.2/bin/agent"
    assert system._validate_cli_install_path("") is None


@pytest.mark.parametrize("mode", ["ask", "retain", "overwrite", "abort", " RETAIN "])
def test_update_local_changes_validation_accepts_supported_modes(mode: str) -> None:
    assert system._validate_update_local_changes(mode) == mode.strip().lower()


def test_update_local_changes_validation_rejects_unknown_mode() -> None:
    with pytest.raises(HTTPException):
        system._validate_update_local_changes("surprise-me")


@pytest.mark.parametrize(
    ("ref", "expected"),
    [
        ("v7.2.0", "v7.2.0"),
        ("7.2.0", "7.2.0"),
        ("main", None),
        ("codex/UI-Update-Improvements", None),
        ("feature/foo", None),
    ],
)
def test_updater_pull_preference_only_for_release_targets(ref: str, expected: str | None) -> None:
    assert system._updater_prefer_pull_ref_for_update_target(ref) == expected


@pytest.mark.parametrize("ref", ["v7.7.4.3-extra", "v7.7.4.3;touch-x", "v7.7", "release-v7.7.4"])
def test_release_tag_detection_rejects_partial_or_suffixed_values(ref: str) -> None:
    assert system._is_semver_tag(ref) is False
    assert system._parse_semver_tag(ref) is None


def test_resolve_update_ref_uses_source_specific_namespace(monkeypatch, tmp_path) -> None:
    calls: list[list[str]] = []
    expected_sha = "a" * 40

    def fake_run(args, **_kwargs):
        calls.append(args)
        if "ls-remote" in args:
            return subprocess.CompletedProcess(
                args,
                0,
                stdout=f"{expected_sha}\trefs/heads/bajaj/maintained\n",
                stderr="",
            )
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    monkeypatch.setattr(system, "_git_available", lambda: True)
    monkeypatch.setattr(system.subprocess, "run", fake_run)

    assert system._resolve_update_ref_sha("bajaj/maintained", "public") == expected_sha
    lookup = calls[0]
    assert lookup[-2:] == ["public", "refs/heads/bajaj/maintained"]
    assert "ls-remote" in lookup
    assert all("fetch" not in call for call in calls)
    assert all("refs/remotes/origin" not in arg for call in calls for arg in call)


def test_remote_updater_context_does_not_write_mounted_checkout(monkeypatch, tmp_path) -> None:
    remote = tmp_path / "remote"
    checkout = tmp_path / "checkout"
    subprocess.run(["git", "init", "-q", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "-C", str(remote), "config", "user.name", "Ava test"], check=True)
    subprocess.run(["git", "-C", str(remote), "config", "user.email", "ava-test@example.invalid"], check=True)
    (remote / "updater").mkdir()
    (remote / "updater" / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(remote), "add", "updater/Dockerfile"], check=True)
    subprocess.run(["git", "-C", str(remote), "commit", "-qm", "fixture"], check=True)
    subprocess.run(["git", "clone", "-q", str(remote), str(checkout)], check=True)
    refs_before = subprocess.run(
        ["git", "-C", str(checkout), "show-ref"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    monkeypatch.setenv("PROJECT_ROOT", str(checkout))

    sha = system._resolve_update_ref_sha("main", "origin")
    assert sha == subprocess.run(
        ["git", "-C", str(remote), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    context = system._materialize_remote_context(str(checkout), "origin", "main", sha)
    try:
        assert Path(context, "updater", "Dockerfile").read_text(encoding="utf-8") == "FROM scratch\n"
        assert not Path(context, ".git").exists()
    finally:
        system.shutil.rmtree(context, ignore_errors=True)

    refs_after = subprocess.run(
        ["git", "-C", str(checkout), "show-ref"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert refs_after == refs_before


@pytest.mark.asyncio
async def test_updates_status_preserves_configured_source_when_remote_has_no_tags(monkeypatch, tmp_path) -> None:
    outputs = iter(
        [
            (0, "bajaj/maintained\n" + "a" * 40 + "\nv7.7.4.3\nv7.7.4.3\n"),
            (0, ""),
        ]
    )

    monkeypatch.setenv("AAVA_UPDATE_REMOTE", "public")
    monkeypatch.setenv("AAVA_UPDATE_DEFAULT_BRANCH", "bajaj/maintained")
    monkeypatch.setattr(system, "_project_host_root_from_admin_ui_container", lambda: str(tmp_path))
    monkeypatch.setattr(system, "_run_updater_ephemeral", lambda *_args, **_kwargs: next(outputs))
    system._UPDATES_STATUS_CACHE.clear()

    response = await system.updates_status(check_remote=True, force=True)

    assert response.remote == {
        "name": "public",
        "default_branch": "bajaj/maintained",
        "latest_tag": "",
        "latest_tag_sha": "",
    }
    assert response.error == "No v* tags found on remote"


@pytest.mark.parametrize(
    ("exit_code", "expected"),
    [
        (0, '{"plan":true}'),
        (1, "error: cannot open '.git/FETCH_HEAD': Permission denied\n"),
    ],
)
def test_ephemeral_plan_keeps_success_json_clean_and_surfaces_failure_stderr(
    monkeypatch, tmp_path, exit_code: int, expected: str
) -> None:
    class FakeContainer:
        def wait(self, timeout: int):
            assert timeout == 30
            return {"StatusCode": exit_code}

        def logs(self, *, stdout: bool, stderr: bool):
            if stdout and not stderr:
                return b'{"plan":true}' if exit_code == 0 else b""
            if not stdout and stderr:
                return b"error: cannot open '.git/FETCH_HEAD': Permission denied\n"
            return b"unexpected combined logs"

        def remove(self, force: bool):
            assert force is True

    container = FakeContainer()

    class FakeContainers:
        def run(self, *_args, **_kwargs):
            return container

        def get(self, _name: str):
            return container

    class FakeDockerClient:
        containers = FakeContainers()

    monkeypatch.setattr(system, "_current_project_head_sha", lambda: "abcdef123456")
    monkeypatch.setattr(system, "_ensure_updater_image_for_ref", lambda *_args, **_kwargs: "updater:test")
    monkeypatch.setattr(system, "_docker_sock_host_path_from_admin_ui_container", lambda: "/var/run/docker.sock")
    monkeypatch.setattr(system.docker, "from_env", lambda: FakeDockerClient())

    code, output = system._run_updater_ephemeral(
        str(tmp_path),
        env={"AAVA_UPDATE_MODE": "plan", "AAVA_UPDATE_REF": "v7.4.0"},
        capture_stderr=False,
    )

    assert code == exit_code
    assert output == expected


@pytest.mark.asyncio
async def test_updates_plan_failure_returns_exact_error_and_cli_recovery(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(system, "_project_host_root_from_admin_ui_container", lambda: str(tmp_path))
    monkeypatch.setattr(
        system,
        "_run_updater_ephemeral",
        lambda *_args, **_kwargs: (1, "mkdir: cannot create directory '/root': Permission denied\n"),
    )

    with pytest.raises(HTTPException) as exc:
        await system.updates_plan(ref="v7.4.0", include_ui=True, checkout=False)

    detail = str(exc.value.detail)
    assert "Updater error:" in detail
    assert "mkdir: cannot create directory '/root': Permission denied" in detail
    assert f"AAVA_REPO={tmp_path}" in detail
    assert "AAVA_CLI_REF=v7.4.0" in detail
    assert "raw.githubusercontent.com/hkjarral" not in detail
    assert 'aava_git ls-remote --get-url origin' in detail
    assert (
        'aava_git status --short '
        '|| { echo "Failed to inspect checkout changes; update not attempted" '
        '>&2; exit 2; }'
    ) in detail
    assert (
        'aava_git diff --binary --cached '
        '| sudo tee "$AAVA_RECOVERY_PATCH" >/dev/null'
    ) in detail
    assert (
        'aava_git diff --binary | sudo tee -a "$AAVA_RECOVERY_PATCH" >/dev/null'
    ) in detail
    assert detail.count("set -o pipefail") == 3
    assert (
        ') || { echo "Failed to preserve staged tracked edits; update not attempted" '
        ">&2; exit 2; }"
    ) in detail
    assert (
        ') || { echo "Failed to preserve unstaged tracked edits; update not attempted" '
        ">&2; exit 2; }"
    ) in detail
    assert "Failed to install selected-ref CLI; update not attempted" in detail
    assert (
        'sudo /usr/local/bin/agent version || { echo "Installed agent CLI is not '
        'runnable; update not attempted" >&2; exit 2; }'
    ) in detail
    assert 'AAVA_RECOVERY_PATCH="$(dirname "$AAVA_REPO")/aava-update-recovery.patch"' in detail
    assert 'cd "$AAVA_REPO"' not in detail
    assert (
        'AAVA_UID="$(sudo stat -c \'%u\' "$AAVA_REPO")" || { '
        'echo "Failed to read checkout owner UID; update not attempted" >&2; exit 2; }'
    ) in detail
    assert (
        'AAVA_GID="$(sudo stat -c \'%g\' "$AAVA_REPO")" || { '
        'echo "Failed to read checkout owner GID; update not attempted" >&2; exit 2; }'
    ) in detail
    assert 'if sudo test -e "$AAVA_REPO/.agent"; then' in detail
    assert 'if sudo test -L "$AAVA_REPO/.agent"; then' in detail
    assert 'if sudo test -L "$AAVA_REPO/.git" || ! sudo test -d "$AAVA_REPO/.git"; then' in detail
    assert 'AAVA_EXPECTED_GIT_DIR="$(sudo realpath -e "$AAVA_REPO/.git")" || exit 2' in detail
    assert 'rev-parse --git-dir' in detail
    assert 'rev-parse --git-common-dir' not in detail
    assert 'rev-parse --absolute-git-dir' not in detail
    assert 'rev-parse --path-format=absolute' not in detail
    assert 'aava_resolve_git_path() {' in detail
    assert 'aava_git() {' in detail
    assert ' --git-dir="$AAVA_REPO/.git" ' in detail
    assert '--work-tree="$AAVA_REPO" "$@"' in detail
    assert ' -C "$AAVA_REPO"' not in detail
    assert (
        'sudo chown -R --no-dereference "$AAVA_UID:$AAVA_GID" '
        '"$AAVA_EXPECTED_GIT_DIR" || exit 2'
    ) in detail
    assert 'if ! sudo test -d "$AAVA_REPO/.agent"; then' in detail
    assert (
        'sudo chown -R --no-dereference "$AAVA_UID:$AAVA_GID" '
        '"$AAVA_REPO/.agent" || { echo "Failed to repair .agent ownership; '
        'update not attempted" >&2; exit 2; }'
    ) in detail
    assert "aava_git ls-files -z" in detail
    assert '[ "${AAVA_REPO%/}" != "$AAVA_REPO" ]' in detail
    assert 'AAVA_REPO="${AAVA_REPO%/}"' in detail
    assert 'case "$AAVA_TRACKED" in' in detail
    assert 'printf \'%s\\0\' "$AAVA_TRACKED_PATH"' in detail
    assert 'sudo test -e "$AAVA_TRACKED_PARENT"' in detail
    assert 'sudo test -L "$AAVA_TRACKED_PARENT"' in detail
    assert 'sort -zu | sudo xargs -0 -r chown --no-dereference' in detail
    assert "Failed to repair tracked checkout ownership; update not attempted" in detail
    assert "find \"$AAVA_REPO\"" not in detail
    assert 'AAVA_TRACKED_PARENT="${AAVA_TRACKED_PATH%/*}"' in detail
    assert 'AAVA_TRACKED_PARENT="${AAVA_TRACKED_PARENT%/*}"' in detail
    assert 'dirname "$AAVA_TRACKED_PATH"' not in detail
    assert "Refusing symlinked tracked parent" in detail
    assert detail.count('AAVA_TRACKED_PARENT="${AAVA_TRACKED_PATH%/*}"') == 2
    assert detail.index('sudo test -L "$AAVA_TRACKED_PARENT"') < detail.index(
        'printf \'%s\\0\' "$AAVA_TRACKED_PATH"'
    )
    assert 'sudo /usr/local/bin/agent update' not in detail
    assert (
        'sudo "$AAVA_SETPRIV" --reuid="$AAVA_UID" --regid="$AAVA_GID" '
        '--groups="$AAVA_GROUPS" /usr/bin/env HOME="$AAVA_HOME" /bin/sh -c '
        '\'cd "$1" && shift && exec "$@"\' sh "$AAVA_REPO" '
        "/usr/local/bin/agent update "
        "--ref v7.4.0 --checkout=false --include-ui=true "
        "--local-changes=retain --self-update=false"
    ) in detail
    assert 'getent passwd "$AAVA_UID"' not in detail
    assert 'sudo find "$AAVA_HOME"' not in detail
    assert 'AAVA_TEMP_HOME="$(sudo mktemp -d /tmp/aava-update-home.XXXXXXXXXX)"' in detail
    assert 'AAVA_TEMP_HOME="$(mktemp -d ' not in detail
    assert 'sudo chown "$AAVA_UID:$AAVA_GID" "$AAVA_TEMP_HOME"' in detail
    assert 'sudo chmod 0700 "$AAVA_TEMP_HOME"' in detail
    assert 'sudo rm -rf -- "$AAVA_TEMP_HOME"' in detail
    assert "AAVA_HOME=/tmp" not in detail
    assert detail.index('sudo chmod 0700 "$AAVA_TEMP_HOME"') < detail.index(
        'sudo chown "$AAVA_UID:$AAVA_GID" "$AAVA_TEMP_HOME"'
    )
    assert "--self-update=true" not in detail


def test_generated_recovery_rejects_symlinked_parent_before_chown(tmp_path) -> None:
    repo = tmp_path / "repo"
    external = tmp_path / "external"
    (external / "nested").mkdir(parents=True)
    (external / "nested" / "file").write_text("outside", encoding="utf-8")
    repo.mkdir()
    (repo / "link").symlink_to(external, target_is_directory=True)

    detail = system._update_plan_failure_detail(
        host_root=str(repo),
        ref="main",
        include_ui=True,
        checkout=True,
        updater_output="permission denied",
    )
    recovery = detail.split("Recovery (run these commands in a host SSH shell):\n", 1)[1]
    start = recovery.index("(\n  set -o pipefail\n  aava_git ls-files -z")
    end = recovery.index("\nAAVA_SETPRIV=", start)
    repair = recovery[start:end]

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    marker = tmp_path / "chown-called"
    fake_chown = fake_bin / "chown"
    fake_chown.write_text(
        '#!/bin/sh\n: > "$AAVA_CHOWN_MARKER"\n',
        encoding="utf-8",
    )
    fake_chown.chmod(0o755)
    env = os.environ.copy()
    env.update(
        {
            "AAVA_CHOWN_MARKER": str(marker),
            "AAVA_GID": str(os.getgid()),
            "AAVA_REPO": str(repo),
            "AAVA_UID": str(os.getuid()),
            "PATH": f"{fake_bin}:{env['PATH']}",
        }
    )
    shell = (
        'sudo() { "$@"; }\n'
        "aava_git() { printf 'link/nested/file\\0'; }\n"
        f"{repair}\n"
    )

    result = subprocess.run(
        ["bash", "-c", shell],
        check=False,
        capture_output=True,
        env=env,
        text=True,
    )

    assert result.returncode == 2
    assert "Refusing symlinked tracked parent" in result.stderr
    assert not marker.exists()


def test_update_plan_recovery_stops_before_update_if_patch_capture_fails(tmp_path) -> None:
    detail = system._update_plan_failure_detail(
        host_root=str(tmp_path / "aava"),
        ref="main",
        include_ui=True,
        checkout=True,
        updater_output="permission denied",
    )

    inspection = 'status --short || { echo "Failed to inspect checkout changes; update not attempted"'
    staged_capture = (
        'aava_git diff --binary --cached '
        '| sudo tee "$AAVA_RECOVERY_PATCH" >/dev/null'
    )
    staged_failure = "Failed to preserve staged tracked edits; update not attempted"
    unstaged_capture = (
        'aava_git diff --binary | sudo tee -a "$AAVA_RECOVERY_PATCH" >/dev/null'
    )
    unstaged_failure = "Failed to preserve unstaged tracked edits; update not attempted"
    installer = "AAVA_CLI_REF=main"
    update = "/usr/local/bin/agent update --ref main"

    assert detail.index(inspection) < detail.index(staged_capture) < detail.index(staged_failure)
    assert detail.index(staged_failure) < detail.index(unstaged_capture)
    assert detail.index(unstaged_capture) < detail.index(unstaged_failure)
    assert detail.index(unstaged_failure) < detail.index(installer) < detail.index(update)


def test_update_plan_recovery_preserves_binary_edits_and_pins_cli(tmp_path) -> None:
    detail = system._update_plan_failure_detail(
        host_root=str(tmp_path / "aava"),
        ref="v7.4.0",
        include_ui=True,
        checkout=False,
        updater_output="permission denied",
    )

    assert 'diff --binary --cached | sudo tee "$AAVA_RECOVERY_PATCH"' in detail
    assert 'diff --binary | sudo tee -a "$AAVA_RECOVERY_PATCH"' in detail
    assert (
        "/usr/local/bin/agent update --ref v7.4.0 --checkout=false "
        "--include-ui=true --local-changes=retain --self-update=false"
    ) in detail
    assert "--self-update=true" not in detail


def test_update_plan_recovery_bounds_git_metadata_repair(tmp_path) -> None:
    detail = system._update_plan_failure_detail(
        host_root=str(tmp_path / "aava"),
        ref="main",
        include_ui=True,
        checkout=True,
        updater_output="permission denied",
    )

    metadata_guard = (
        'if sudo test -L "$AAVA_REPO/.git" || ! sudo test -d "$AAVA_REPO/.git"; then'
    )
    expected = 'AAVA_EXPECTED_GIT_DIR="$(sudo realpath -e "$AAVA_REPO/.git")" || exit 2'
    resolved = 'AAVA_GIT_DIR_RAW="$(aava_git rev-parse --git-dir)"'
    boundary = 'if [ "$AAVA_GIT_DIR" != "$AAVA_EXPECTED_GIT_DIR" ]; then'
    refusal = "Refusing Git metadata repair outside %s"
    repair = (
        'sudo chown -R --no-dereference "$AAVA_UID:$AAVA_GID" '
        '"$AAVA_EXPECTED_GIT_DIR" || exit 2'
    )

    assert metadata_guard in detail
    assert boundary in detail
    assert refusal in detail
    assert repair in detail
    assert "AAVA_GIT_COMMON_DIR" not in detail
    assert detail.index(metadata_guard) < detail.index(expected) < detail.index(resolved)
    assert detail.index(resolved) < detail.index(boundary) < detail.index(repair)


def test_update_plan_recovery_stops_before_repair_if_cli_bootstrap_fails(tmp_path) -> None:
    detail = system._update_plan_failure_detail(
        host_root=str(tmp_path / "aava"),
        ref="main",
        include_ui=True,
        checkout=True,
        updater_output="permission denied",
    )

    bootstrap = "git clone --quiet --depth 1 --single-branch"
    bootstrap_failure = "Failed to fetch selected CLI source; update not attempted"
    version = "sudo /usr/local/bin/agent version"
    version_failure = "Installed agent CLI is not runnable; update not attempted"
    repair = 'AAVA_UID="$(sudo stat'
    update = "/usr/local/bin/agent update --ref main"

    assert detail.index(bootstrap) < detail.index(bootstrap_failure)
    assert detail.index(bootstrap_failure) < detail.index(version)
    assert detail.index(version) < detail.index(version_failure)
    assert detail.index(version_failure) < detail.index(repair) < detail.index(update)


def test_update_plan_branch_recovery_builds_cli_from_exact_selected_ref(tmp_path) -> None:
    detail = system._update_plan_failure_detail(
        host_root=str(tmp_path / "aava"),
        ref="codex/upgrade-improvements",
        include_ui=True,
        checkout=True,
        updater_output="permission denied",
    )

    assert "AAVA_CLI_REF=codex/upgrade-improvements" in detail
    assert (
        'AAVA_CLI_REMOTE="$(aava_git ls-remote --get-url origin)"'
    ) in detail
    assert "config --get remote.origin.url" not in detail
    assert '--branch "$AAVA_CLI_REF"' in detail
    assert '-- "$AAVA_CLI_REMOTE" "$AAVA_CLI_SRC/repo"' in detail
    assert '-e AAVA_CLI_VERSION="$AAVA_CLI_REF" golang:1.22-bookworm' in detail
    assert '-o /out/agent ./cmd/agent' in detail
    assert 'sudo install -m 0755 "$AAVA_CLI_SRC/out/agent" /usr/local/bin/agent' in detail
    assert "Failed to fetch selected CLI source; update not attempted" in detail
    assert "Failed to build CLI from selected ref; update not attempted" in detail
    assert "Failed to install selected-ref CLI; update not attempted" in detail
    assert "AGENT_VERSION=latest" not in detail
    assert "scripts/install-cli.sh" not in detail
    assert "https://github.com/hkjarral/AVA-AI-Voice-Agent-for-Asterisk.git" not in detail
    assert detail.index("ls-remote --get-url origin") < detail.index("git clone --quiet")


def test_update_plan_recovery_fails_closed_on_owner_or_agent_repair_errors(tmp_path) -> None:
    detail = system._update_plan_failure_detail(
        host_root=str(tmp_path / "aava"),
        ref="main",
        include_ui=True,
        checkout=True,
        updater_output="permission denied",
    )

    uid_lookup = 'AAVA_UID="$(sudo stat -c \'%u\' "$AAVA_REPO")"'
    uid_failure = "Failed to read checkout owner UID; update not attempted"
    gid_lookup = 'AAVA_GID="$(sudo stat -c \'%g\' "$AAVA_REPO")"'
    gid_failure = "Failed to read checkout owner GID; update not attempted"
    agent_type_guard = 'if ! sudo test -d "$AAVA_REPO/.agent"; then'
    agent_repair = (
        'sudo chown -R --no-dereference "$AAVA_UID:$AAVA_GID" '
        '"$AAVA_REPO/.agent" || {'
    )
    agent_failure = "Failed to repair .agent ownership; update not attempted"
    update = "/usr/local/bin/agent update --ref main"

    assert detail.index(uid_lookup) < detail.index(uid_failure)
    assert detail.index(uid_failure) < detail.index(gid_lookup) < detail.index(gid_failure)
    assert detail.index(gid_failure) < detail.index(agent_type_guard)
    assert detail.index(agent_type_guard) < detail.index(agent_repair)
    assert detail.index(agent_repair) < detail.index(agent_failure) < detail.index(update)


def test_update_plan_recovery_restores_temporary_parent_traversal(tmp_path) -> None:
    detail = system._update_plan_failure_detail(
        host_root=str(tmp_path / "private" / "aava"),
        ref="main",
        include_ui=True,
        checkout=True,
        updater_output="permission denied",
    )

    state = 'AAVA_TRAVERSAL_STATE="$(mktemp)" || exit 2'
    parent_loop = 'while [ "$AAVA_PARENT" != "/" ]; do'
    access_probe = (
        'sudo "$AAVA_SETPRIV" --reuid="$AAVA_UID" --regid="$AAVA_GID" '
        '--groups="$AAVA_GROUPS" test -x "$AAVA_PARENT"'
    )
    grant = 'sudo chmod o+x -- "$AAVA_PARENT" || exit 2'
    restore = 'sudo chmod "$AAVA_MODE" -- "$AAVA_PARENT" || AAVA_RESTORE_STATUS=2'
    update = "/usr/local/bin/agent update --ref main"

    assert state in detail
    assert parent_loop in detail
    assert access_probe in detail
    assert grant in detail
    assert restore in detail
    assert 'trap \'AAVA_EXIT=$?; aava_restore_traversal' in detail
    assert "trap 'exit 129' HUP" in detail
    assert "trap 'exit 130' INT" in detail
    assert "trap 'exit 143' TERM" in detail
    assert detail.index(state) < detail.index(parent_loop)
    assert detail.index(restore) < detail.index(grant) < detail.index(update)


def test_update_plan_recovery_enters_repo_after_parent_traversal(tmp_path) -> None:
    detail = system._update_plan_failure_detail(
        host_root=str(tmp_path / "private" / "aava"),
        ref="main",
        include_ui=True,
        checkout=True,
        updater_output="permission denied",
    )

    traversal = 'while [ "$AAVA_PARENT" != "/" ]; do'
    owner_shell = '/bin/sh -c \'cd "$1" && shift && exec "$@"\' sh "$AAVA_REPO"'
    update = "/usr/local/bin/agent update --ref main"

    assert owner_shell in detail
    assert detail.index(traversal) < detail.index(owner_shell) < detail.index(update)


def test_update_plan_recovery_adds_docker_socket_gid_to_target_groups(tmp_path) -> None:
    detail = system._update_plan_failure_detail(
        host_root=str(tmp_path / "aava"),
        ref="main",
        include_ui=True,
        checkout=True,
        updater_output="permission denied",
    )

    setpriv = 'AAVA_SETPRIV="$(command -v setpriv)"'
    target_groups = 'sudo -u "#$AAVA_UID" -g "#$AAVA_GID" id -G'
    socket_gid = 'AAVA_DOCKER_GID="$(sudo stat -c \'%g\' /var/run/docker.sock)"'
    append_socket_gid = 'AAVA_GROUPS="${AAVA_GROUPS},${AAVA_DOCKER_GID}"'
    update = (
        'sudo "$AAVA_SETPRIV" --reuid="$AAVA_UID" --regid="$AAVA_GID" '
        '--groups="$AAVA_GROUPS" /usr/bin/env HOME="$AAVA_HOME" /bin/sh -c '
        '\'cd "$1" && shift && exec "$@"\' sh "$AAVA_REPO" '
        "/usr/local/bin/agent update"
    )

    assert setpriv in detail
    assert target_groups in detail
    assert "if sudo test -S /var/run/docker.sock; then" in detail
    assert socket_gid in detail
    assert append_socket_gid in detail
    assert update in detail
    assert "--preserve-groups" not in detail
    assert detail.index(target_groups) < detail.index(socket_gid) < detail.index(update)


def test_update_plan_failure_preserves_long_stderr_and_explicit_flags(tmp_path) -> None:
    updater_output = "root cause before long diagnostic\n" + ("x" * 5000) + "\nfinal error"

    detail = system._update_plan_failure_detail(
        host_root=str(tmp_path),
        ref="main",
        include_ui=False,
        checkout=True,
        updater_output=updater_output,
    )

    assert updater_output in detail
    assert (
        "agent update --ref main --checkout=true --include-ui=false "
        "--local-changes=retain --self-update=false"
    ) in detail


@pytest.mark.parametrize("ref", ["7.4.0", "v7.4.0"])
def test_update_plan_failure_normalizes_recovery_cli_release_tag(tmp_path, ref: str) -> None:
    detail = system._update_plan_failure_detail(
        host_root=str(tmp_path),
        ref=ref,
        include_ui=True,
        checkout=False,
        updater_output="plan failed",
    )

    assert "AAVA_CLI_REF=v7.4.0" in detail
    assert 'git clone --quiet --depth 1 --single-branch --branch "$AAVA_CLI_REF"' in detail
    assert "raw.githubusercontent.com/hkjarral" not in detail
    assert f"agent update --ref {ref}" in detail


def test_ai_engine_sessions_stats_urls_use_configured_health_port(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("AI_ENGINE_HEALTH_URL", raising=False)
    monkeypatch.delenv("HEALTH_BIND_PORT", raising=False)
    monkeypatch.setattr(system, "_dotenv_value", lambda key: "18000" if key == "HEALTH_BIND_PORT" else None)

    urls = system._ai_engine_sessions_stats_urls()

    assert "http://127.0.0.1:18000/sessions/stats" in urls
    assert "http://ai_engine:18000/sessions/stats" in urls
    assert "http://ai-engine:18000/sessions/stats" in urls


def test_configured_ai_engine_health_port_reads_yaml(monkeypatch, tmp_path) -> None:
    import settings

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    base = config_dir / "ai-agent.yaml"
    local = config_dir / "ai-agent.local.yaml"
    base.write_text("health:\n  port: 16000\n", encoding="utf-8")
    local.write_text("health:\n  port: 17000\n", encoding="utf-8")

    monkeypatch.delenv("HEALTH_BIND_PORT", raising=False)
    monkeypatch.setattr(system, "_dotenv_value", lambda _key: None)
    monkeypatch.setattr(settings, "CONFIG_PATH", str(base))
    monkeypatch.setattr(settings, "LOCAL_CONFIG_PATH", str(local))

    assert system._configured_ai_engine_health_port() == 17000


def test_ensure_updater_image_for_ref_uses_cached_local_tag(monkeypatch, tmp_path) -> None:
    local_tag = "aava-updater:sha-cached"

    class FakeImages:
        def get(self, tag: str):
            assert tag == local_tag
            return object()

    class FakeDockerClient:
        images = FakeImages()

    monkeypatch.setattr(system.docker, "from_env", lambda: FakeDockerClient())
    monkeypatch.setattr(
        system,
        "_run_docker_with_updater_status",
        lambda *_args, **_kwargs: pytest.fail("cached updater image should not pull"),
    )
    monkeypatch.setattr(
        system,
        "_ensure_updater_image_for_sha",
        lambda *_args, **_kwargs: pytest.fail("cached updater image should not build"),
    )
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))

    got = system._ensure_updater_image_for_ref(
        str(tmp_path),
        local_tag,
        prefer_pull_ref="latest",
        allow_build=False,
    )

    assert got == local_tag


def test_updater_build_embeds_source_version_in_cli(monkeypatch, tmp_path) -> None:
    captured: dict[str, object] = {}

    class MissingImages:
        def get(self, _tag: str):
            raise RuntimeError("not cached")

    class FakeDockerClient:
        images = MissingImages()

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return 0, "built"

    monkeypatch.setattr(system.docker, "from_env", lambda: FakeDockerClient())
    monkeypatch.setattr(system, "_run_docker_with_updater_status", fake_run)
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))

    tag = system._ensure_updater_image_for_sha(
        str(tmp_path),
        "aava-updater:test",
        require_local_source=True,
        source_sha="abcdef1234567890",
    )

    assert tag == "aava-updater:test"
    args = captured["args"]
    assert isinstance(args, list)
    assert ["--build-arg", "AAVA_CLI_VERSION=abcdef123456"] == args[
        args.index("--build-arg") : args.index("--build-arg") + 2
    ]


@pytest.mark.parametrize(
    "value",
    [
        "agent",
        "/opt/agent;rm",
        "/opt/agent $(touch x)",
        "/opt/../agent",
        "/opt/agent name",
        "/opt/agent\x00x",
    ],
)
def test_cli_install_path_validation_rejects_unsafe_paths(value: str) -> None:
    with pytest.raises(HTTPException) as exc:
        system._validate_cli_install_path(value)
    assert exc.value.status_code == 400


def test_read_update_job_marks_running_job_stale(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    job_id = uuid.uuid4().hex
    state = _jobs_dir(tmp_path) / f"{job_id}.json"
    state.write_text(
        '{"job_id":"%s","status":"running","started_at":"2020-01-01T00:00:00Z"}' % job_id,
        encoding="utf-8",
    )
    old = time.time() - system._UPDATE_STALE_AFTER_SEC - 60
    os.utime(state, (old, old))

    job, _state_path, _log_path = system._read_update_job(job_id)

    assert job["status"] == "stale"
    assert job["stale"] is True
    assert "heartbeat" in job["failure_reason"]


def test_find_active_update_job_ignores_stale_jobs(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    jobs = _jobs_dir(tmp_path)
    stale_id = uuid.uuid4().hex
    active_id = uuid.uuid4().hex

    active_state = jobs / f"{active_id}.json"
    active_state.write_text('{"job_id":"%s","status":"running"}' % active_id, encoding="utf-8")

    stale_state = jobs / f"{stale_id}.json"
    stale_state.write_text(
        '{"job_id":"%s","status":"running","started_at":"2020-01-01T00:00:00Z"}' % stale_id,
        encoding="utf-8",
    )

    def fake_stale(job: dict, **_kwargs) -> bool:
        return job.get("job_id") == stale_id

    monkeypatch.setattr(system, "_is_update_job_stale", fake_stale)

    active = system._find_active_update_job()

    assert active is not None
    assert active["job_id"] == active_id


@pytest.mark.asyncio
async def test_updates_job_log_returns_full_log(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    job_id = uuid.uuid4().hex
    log = _jobs_dir(tmp_path) / f"{job_id}.log"
    log.write_text("line 1\nline 2\n", encoding="utf-8")

    response = await system.updates_job_log(job_id)

    assert response.job_id == job_id
    assert response.log == "line 1\nline 2\n"


@pytest.mark.asyncio
async def test_updater_image_status_reads_persisted_progress(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))

    system._write_updater_image_status(
        status="running",
        phase="building",
        image="aava-updater:test",
        message="Building updater image from local source",
        detail_tail=["#1 loading", "#2 building"],
        started_at="2026-01-01T00:00:00Z",
    )

    response = await system.updates_updater_image_status()

    assert response.status["status"] == "running"
    assert response.status["phase"] == "building"
    assert response.status["image"] == "aava-updater:test"
    assert response.status["detail_tail"] == ["#1 loading", "#2 building"]
