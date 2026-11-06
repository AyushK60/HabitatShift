"""Reproducibility manifest for an M1 run.

The manifest is a superset of the study summary: it additionally records the
catalogue search, per-observation provenance, processing parameters and file
hashes.  It is validated against :data:`M1_MANIFEST_SCHEMA` before writing, so a
run cannot publish a manifest that omits scene IDs, dates, the grid, formulas,
thresholds, versions or hashes.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

import jsonschema

from ..provenance.manifest import describe_output, sha256_file


M1_MANIFEST_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "HabitatShift M1 science-engine manifest",
    "type": "object",
    "required": [
        "manifest_version",
        "generated_utc",
        "experiment_id",
        "study",
        "aoi",
        "grid",
        "catalog",
        "periods",
        "indices",
        "change",
        "processing",
        "outputs",
        "software",
        "attribution",
        "verification",
        "limitations",
    ],
    "additionalProperties": True,
    "properties": {
        "manifest_version": {"const": "m1-1.0"},
        "generated_utc": {"type": "string", "format": "date-time"},
        "experiment_id": {"type": "string", "minLength": 1},
        "study": {
            "type": "object",
            "required": ["study_id", "title", "study_type", "question"],
            "properties": {
                "study_id": {"type": "string", "minLength": 1},
                "title": {"type": "string", "minLength": 1},
                "study_type": {"type": "string", "minLength": 1},
                "question": {"type": "string", "minLength": 1},
            },
        },
        "aoi": {
            "type": "object",
            "required": ["geojson", "bounds_4326", "analysis_crs", "area_km2"],
            "properties": {
                "geojson": {"type": "object"},
                "bounds_4326": {"type": "array", "minItems": 4, "maxItems": 4},
                "analysis_crs": {"type": "string", "minLength": 4},
                "area_km2": {"type": "number", "exclusiveMinimum": 0},
            },
        },
        "grid": {
            "type": "object",
            "required": [
                "crs", "resolution_m", "width", "height", "transform", "signature",
            ],
            "properties": {
                "crs": {"type": "string", "minLength": 4},
                "resolution_m": {"type": "number", "exclusiveMinimum": 0},
                "width": {"type": "integer", "exclusiveMinimum": 0},
                "height": {"type": "integer", "exclusiveMinimum": 0},
                "transform": {"type": "array", "minItems": 6, "maxItems": 6},
                "signature": {"type": "string", "minLength": 8},
            },
        },
        "catalog": {
            "type": "object",
            "required": ["endpoint", "collection", "provider", "license"],
        },
        "periods": {
            "type": "array",
            "minItems": 2,
            "items": {
                "type": "object",
                "required": [
                    "period_id",
                    "anchor_date",
                    "observation_dates",
                    "item_ids",
                    "composite_method",
                    "observation_count",
                    "valid_fraction",
                    "indices",
                ],
                "properties": {
                    "period_id": {"enum": ["earlier", "later"]},
                    "anchor_date": {"type": "string", "minLength": 10},
                    "observation_dates": {
                        "type": "array", "minItems": 1, "items": {"type": "string"}
                    },
                    "item_ids": {
                        "type": "array", "minItems": 1, "items": {"type": "string"}
                    },
                    "composite_method": {"type": "string"},
                    "observation_count": {"type": "integer", "minimum": 1},
                    "valid_fraction": {
                        "type": "number", "minimum": 0, "maximum": 1
                    },
                    "indices": {"type": "object", "minProperties": 1},
                },
            },
        },
        "indices": {"type": "object", "minProperties": 1},
        "change": {"type": "object", "minProperties": 1},
        "processing": {
            "type": "object",
            "required": ["pipeline_version", "profile", "operations", "parameters"],
        },
        "outputs": {"type": "object", "minProperties": 1},
        "software": {"type": "object", "minProperties": 1},
        "attribution": {
            "type": "object",
            "required": ["text", "license", "access_date_utc"],
        },
        "verification": {"type": "object"},
        "limitations": {"type": "array", "items": {"type": "string"}},
    },
}


class M1ManifestError(ValueError):
    """Raised when an M1 manifest is structurally incomplete."""


class M1ManifestBuilder:
    """Accumulate manifest sections, validate once, then write."""

    def __init__(self) -> None:
        self.data: dict[str, Any] = {
            "manifest_version": "m1-1.0",
            "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        }

    def set(self, key: str, value: Any) -> "M1ManifestBuilder":
        self.data[key] = value
        return self

    def update(self, values: dict[str, Any]) -> "M1ManifestBuilder":
        self.data.update(values)
        return self

    def validate(self) -> None:
        errors = sorted(
            jsonschema.Draft202012Validator(M1_MANIFEST_SCHEMA).iter_errors(
                self.data
            ),
            key=lambda e: list(e.path),
        )
        if errors:
            rendered = "; ".join(
                f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"
                for e in errors[:8]
            )
            raise M1ManifestError(f"M1 manifest incomplete: {rendered}")

    def write(self, path: Path) -> Path:
        self.validate()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        return path


def validate_m1_manifest(payload: dict[str, Any]) -> None:
    jsonschema.Draft202012Validator(M1_MANIFEST_SCHEMA).validate(payload)


def output_record(path: Path, kind: str) -> dict[str, Any]:
    """Output record with portable path, byte size and checksum."""
    return describe_output(path, kind)


def hash_outputs(outputs: dict[str, dict[str, Any]]) -> dict[str, str]:
    """Map portable paths to hashes for quick manifest cross-checking."""
    return {record["path"]: record["sha256"] for record in outputs.values()}


__all__ = [
    "M1_MANIFEST_SCHEMA",
    "M1ManifestBuilder",
    "M1ManifestError",
    "hash_outputs",
    "output_record",
    "sha256_file",
    "validate_m1_manifest",
]
