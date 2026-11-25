"""Regression checks for Ava batch transcription when its GPU mapping is stale."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


SOURCE = Path(__file__).parents[1] / "local_ai_server" / "batch_stt_worker.py"
SPEC = importlib.util.spec_from_file_location("batch_stt_worker", SOURCE)
assert SPEC and SPEC.loader
worker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(worker)


def _args(model: str = "base", device: str = "cuda") -> SimpleNamespace:
    return SimpleNamespace(
        backend="faster_whisper", model=model, device=device,
        compute_type="float16", configured_language="en", language="",
    )


def test_gpu_initialization_loss_uses_bounded_cpu_batch_fallback(monkeypatch):
    calls = []

    class Backend:
        def __init__(self, **kwargs):
            self.device = kwargs["device"]
            calls.append(("create", self.device, kwargs["compute_type"]))

        def initialize(self):
            calls.append(("initialize", self.device))
            return self.device == "cpu"

        def transcribe_pcm16(self, data, **kwargs):
            assert data == b"\x00\x00"
            calls.append(("transcribe", self.device))
            return "Please call back"

        def shutdown(self):
            calls.append(("shutdown", self.device))

    monkeypatch.setitem(sys.modules, "stt_backends", SimpleNamespace(FasterWhisperSTTBackend=Backend))
    assert worker._transcribe(_args(), b"\x00\x00") == "Please call back"
    assert calls == [
        ("create", "cuda", "float16"), ("initialize", "cuda"),
        ("shutdown", "cuda"), ("create", "cpu", "int8"),
        ("initialize", "cpu"), ("transcribe", "cpu"), ("shutdown", "cpu"),
    ]


@pytest.mark.parametrize("model,device", [("medium", "cuda"), ("base", "cpu")])
def test_cpu_fallback_does_not_expand_to_unbounded_models_or_non_gpu_failures(
    monkeypatch, model, device
):
    attempts = []

    class Backend:
        def __init__(self, **kwargs):
            attempts.append(kwargs["device"])

        def initialize(self):
            return False

        def shutdown(self):
            pass

    monkeypatch.setitem(sys.modules, "stt_backends", SimpleNamespace(FasterWhisperSTTBackend=Backend))
    with pytest.raises(RuntimeError, match="stt_unavailable"):
        worker._transcribe(_args(model, device), b"\x00\x00")
    assert attempts == [device]


def test_healthy_gpu_batch_does_not_start_a_second_model(monkeypatch):
    attempts = []

    class Backend:
        def __init__(self, **kwargs):
            attempts.append(kwargs["device"])

        def initialize(self):
            return True

        def transcribe_pcm16(self, *_args, **_kwargs):
            return "Ready"

        def shutdown(self):
            pass

    monkeypatch.setitem(sys.modules, "stt_backends", SimpleNamespace(FasterWhisperSTTBackend=Backend))
    assert worker._transcribe(_args(), b"\x00\x00") == "Ready"
    assert attempts == ["cuda"]


@pytest.mark.parametrize("message,should_fallback", [
    ("CUDA failed with error no CUDA-capable device is detected", True),
    ("audio decode failed", False),
])
def test_cuda_failure_during_transcription_is_bounded(monkeypatch, message, should_fallback):
    attempts = []

    class Backend:
        def __init__(self, **kwargs):
            self.device = kwargs["device"]
            attempts.append(("create", self.device))

        def initialize(self):
            return True

        def transcribe_pcm16(self, *_args, **_kwargs):
            if self.device == "cuda":
                raise RuntimeError(message)
            return "Message received"

        def shutdown(self):
            attempts.append(("shutdown", self.device))

    monkeypatch.setitem(sys.modules, "stt_backends", SimpleNamespace(FasterWhisperSTTBackend=Backend))
    if should_fallback:
        assert worker._transcribe(_args(), b"\x00\x00") == "Message received"
        assert attempts == [
            ("create", "cuda"), ("shutdown", "cuda"),
            ("create", "cpu"), ("shutdown", "cpu"),
        ]
    else:
        with pytest.raises(RuntimeError, match="audio decode failed"):
            worker._transcribe(_args(), b"\x00\x00")
        assert attempts == [("create", "cuda"), ("shutdown", "cuda")]
