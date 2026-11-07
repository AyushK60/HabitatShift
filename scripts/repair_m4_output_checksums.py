"""M5-G1 correction: refresh drifted output checksums in the M4 run manifests.

Root cause (found by the M5-G1 independent audit): M4-R1 G4's
``scripts/regenerate_comparable_previews.py`` re-rendered the true/false
colour composite PNGs and rewrote each ``summary.json`` (joint-stretch
provenance fields) but did not refresh the ``outputs`` sha256 records in the
run manifests.  Every scientific output (reflectance/index/delta/change
rasters, GeoTIFFs) still verifies byte-for-byte; only the four colour PNGs
and the summary JSON drifted, and only through visual-stretch re-rendering.

This script makes the recorded provenance match the artifacts that actually
exist on disk, for those drifted outputs only.  It refuses to touch any
output whose file is missing, and it prints a per-manifest before/after
summary.  Backups of the manifests are written next to this script's output
directory before anything is modified.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKUP_DIR = ROOT / "docs" / "evidence" / "m5" / "backup_manifests_before_checksum_repair"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    manifest_dir = ROOT / "data" / "manifests"
    report: dict[str, dict] = {}
    for manifest_path in sorted(manifest_dir.glob("m4_*.json")):
        manifest = json.loads(manifest_path.read_text())
        drifted = []
        for name, meta in manifest.get("outputs", {}).items():
            path = ROOT / meta["path"]
            if not path.exists():
                print(f"REFUSING: {manifest_path.name}/{name}: output missing ({meta['path']})")
                return 2
            actual = sha256_file(path)
            if actual != meta["sha256"]:
                drifted.append(name)
                meta["sha256"] = actual
        if not drifted:
            report[manifest_path.name] = {"drifted": []}
            continue
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        backup = BACKUP_DIR / manifest_path.name
        if not backup.exists():
            shutil.copy2(manifest_path, backup)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        report[manifest_path.name] = {"drifted": drifted}
        print(f"{manifest_path.name}: refreshed {len(drifted)} checksums: {sorted(drifted)}")

    # verify: nothing but the outputs sections changed
    print("\nverification:")
    all_ok = True
    for manifest_path in sorted(manifest_dir.glob("m4_*.json")):
        backup = BACKUP_DIR / manifest_path.name
        if not backup.exists():
            continue
        before = json.loads(backup.read_text())
        after = json.loads(manifest_path.read_text())
        changed_keys = set()
        for key in set(before) | set(after):
            if before.get(key) != after.get(key):
                changed_keys.add(key)
        outputs_only = changed_keys <= {"outputs"}
        print(f"  {manifest_path.name}: changed top-level keys {sorted(changed_keys)} — outputs-only: {outputs_only}")
        all_ok = all_ok and outputs_only
        for name, meta in after["outputs"].items():
            actual = sha256_file(ROOT / meta["path"])
            if actual != meta["sha256"]:
                print(f"  STILL MISMATCHED: {manifest_path.name}/{name}")
                all_ok = False
    print("\nchecksum repair:", "verified" if all_ok else "FAILED")
    return 0 if all_ok else 2


if __name__ == "__main__":
    sys.exit(main())
