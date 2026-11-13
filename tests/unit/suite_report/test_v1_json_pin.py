"""v1 CLI JSON hashes captured before the R1 runtime changes."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from arci.cli import main

# Captured from the unchanged 2.0.0 report route, including its trailing newline.
RECORDED = {
    "guardrail/2026-10-05/guardrail-live-b-all-provider_down-200": (
        "11a2bfc1bdf71d75d2fd599997a24263c90b3b60b88d658110607e07eb11a925"
    ),
    "guardrail/2026-10-05/guardrail-live-b-ask-clean-1": (
        "989711dd7b670c17e824119a476025313f32c31fa8b9ff873017b7995e53ff9f"
    ),
    "guardrail/2026-10-05/guardrail-live-b-ask-low_confidence-50": (
        "22052a91f4b8ab07442ae00ddad11fcd360d6f99110a17939ae18a83a4137164"
    ),
    "guardrail/2026-10-05/guardrail-live-b-ask-provider_down-200": (
        "7b9a5cf12c6b64ebf6160ee5210e00758979101096109456fd0dae261db630c8"
    ),
    "guardrail/2026-10-05/guardrail-live-b-ask-provider_down-50": (
        "32ccf07d11e0b77e3408bd188552d810d81c851cf8d13d629ba9162e902ecc75"
    ),
    "guardrail/2026-10-05/guardrail-live-c-ask-clean-50": (
        "08b1c5620ff1dc984711a72dbd671c7803176e6234c3f1a3db7ba5da0564f57d"
    ),
    "jev/2026-10-03/attempt-1-invalid/jev-live-a-low_confidence-50": (
        "fcc7cd31182f9cbd530b4e6a6858b1b7b47365e3ba240739c78c16d72d388ec7"
    ),
    "jev/2026-10-03/attempt-1-invalid/jev-live-b-clean-1": (
        "c3714df6aa93a7583a9e97f2b7523fa3e0ad49274e06dcd7fc05b9b9911cf838"
    ),
    "jev/2026-10-03/attempt-1-invalid/jev-live-b-low_confidence-200": (
        "a32f342c6ba280f2ec733bed5d3430bec34ae0e47ea512f321ebbc919cafd2de"
    ),
    "jev/2026-10-03/attempt-1-invalid/jev-live-b-low_confidence-50": (
        "cadb43666b0929073ca09056a090873ff397b7f8f03c1f1f0af7c53fdde72514"
    ),
    "jev/2026-10-03/attempt-1-invalid/jev-live-b-low_confidence-50-node": (
        "6c88761a696ae84c48baa83713dd6b9d0a8780c2edf2ba396ebd5122e9d48b50"
    ),
    "jev/2026-10-03/attempt-1-invalid/jev-live-c-low_confidence-50": (
        "d770e48736668290e49beb1dd0764ad0c25f7741c706757d73150bb65ea1a239"
    ),
    "jev/2026-10-03/jev-live-a-low_confidence-50": (
        "4c1f69ad3754506f1e8b03f9b2281d8833599a6f77221c6a04fcf3d024eab952"
    ),
    "jev/2026-10-03/jev-live-b-clean-1": (
        "084b7e1674eb5381326cdcbde2a62b862cd917d2df48d32b19e3c69a9d137cbe"
    ),
    "jev/2026-10-03/jev-live-b-clean-50": (
        "d3290dc1581ead786848154c6a39d19c29e4ac258cee0e3d751d19be7fa22654"
    ),
    "jev/2026-10-03/jev-live-b-low_confidence-200": (
        "d9ef57fe5af6e326aa960189d98488ce7c36eb81c808f9a3cde53973160e8e34"
    ),
    "jev/2026-10-03/jev-live-b-low_confidence-50": (
        "3ed4e7ed7c42936b0a4460105a229733f9811522ef90da0251dcf396bfb75a7a"
    ),
    "jev/2026-10-03/jev-live-b-low_confidence-50-node": (
        "8cd5bf185333827bb76b2f8043e22285692588a31bf09328e26bef6f9cc03af6"
    ),
    "jev/2026-10-03/jev-live-c-low_confidence-50": (
        "abe3691ef8a063da57742f5ed0598cca46ab0f13d3553d095cadf5204daa2d8b"
    ),
}


@pytest.mark.parametrize("store", sorted(RECORDED))
def test_v1_json_byte_pin(store: str, capsys: pytest.CaptureFixture[str]) -> None:
    root = Path(__file__).resolve().parents[3] / "docs" / "results"
    assert main(["report", str(root / store), "--format", "json"]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert hashlib.sha256(captured.out.encode("utf-8")).hexdigest() == RECORDED[store]
