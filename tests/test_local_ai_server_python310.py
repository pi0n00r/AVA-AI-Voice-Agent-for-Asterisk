"""Keep batch STT compatible with the production CUDA image's Python 3.10."""

import asyncio
import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "local_ai_server"))
import server as local_server  # noqa: E402


def test_batch_worker_uses_python310_timeout_and_returns_transcript(monkeypatch):
    class FakeProcess:
        returncode = 0

        async def communicate(self, pcm16):
            assert pcm16 == b"test-pcm"
            return json.dumps({"status": "ok", "text": "front door"}).encode(), b""

        async def wait(self):
            return 0

        def kill(self):
            raise AssertionError("successful worker must not be killed")

    async def fake_spawn(*args, **kwargs):
        return FakeProcess()

    monkeypatch.setattr(local_server.asyncio, "create_subprocess_exec", fake_spawn)
    worker = object.__new__(local_server.LocalAIServer)
    worker.stt_backend = "faster_whisper"
    worker.faster_whisper_backend = object()
    worker.faster_whisper_model = "base"
    worker.faster_whisper_language = "en"
    worker.faster_whisper_device = "cuda"
    worker.faster_whisper_compute = "float16"
    worker._batch_preempted = False
    worker._live_session_ids = set()
    worker._batch_process = None

    assert asyncio.run(worker._run_batch_worker(b"test-pcm", None)) == "front door"
    assert worker._batch_process is None
    # asyncio.timeout is unavailable in the Python 3.10 production GPU image.
    assert "timeout" not in local_server.LocalAIServer._run_batch_worker.__code__.co_names
