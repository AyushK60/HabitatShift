"""Regression test (M5-G1): every manifest output checksum must match its file.

The M5 audit found that ``scripts/regenerate_comparable_previews.py`` (M4-R1
G4) re-rendered preview PNGs and rewrote ``summary.json`` without refreshing
the ``outputs`` sha256 records in the run manifests, leaving six M4 manifests
with stale provenance.  This test walks every run manifest in
``data/manifests`` and asserts each recorded output still exists and hashes
to its recorded SHA-256, so any future regeneration that rewrites an artifact
without updating provenance fails immediately.

Runs in the offline tier: it only reads already-downloaded artifacts.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_DIR = PROJECT_ROOT / "data" / "manifests"

def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_every_manifest_output_checksum_matches_its_file() -> None:
    manifests = sorted(MANIFEST_DIR.glob("*.json"))
    assert manifests, "no run manifests found in data/manifests"

    mismatches: list[str] = []
    missing: list[str] = []
    checked = 0
    for manifest_path in manifests:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        outputs = manifest.get("outputs") or {}
        assert outputs, f"{manifest_path.name}: manifest records no outputs"
        for name, meta in outputs.items():
            path = PROJECT_ROOT / meta["path"]
            if not path.exists():
                missing.append(f"{manifest_path.name}/{name}: {meta['path']}")
                continue
            checked += 1
            if _sha256(path) != meta["sha256"]:
                mismatches.append(f"{manifest_path.name}/{name}: {meta['path']}")

    assert not missing, (
        "manifest outputs missing on disk: " + "; ".join(missing)
    )
    assert not mismatches, (
        "manifest output checksums do not match the files on disk "
        "(re-run the artifact's provenance update step): " + "; ".join(mismatches)
    )
    assert checked >= 50, f"expected the full output inventory, checked only {checked}"
