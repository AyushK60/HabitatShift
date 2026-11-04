"""Provenance manifest construction and schema validation.

Manifests are generated from the same values the pipeline actually used, then
validated against :data:`MANIFEST_SCHEMA` before being written.  A manifest that
omits a required provenance field cannot be saved.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

import jsonschema

from .. import config

MANIFEST_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "HabitatShift M0 primary study manifest",
    "type": "object",
    "required": [
        "manifest_version",
        "generated_utc",
        "study",
        "aoi",
        "catalog",
        "periods",
        "processing",
        "outputs",
        "software",
        "attribution",
        "validity",
    ],
    "additionalProperties": True,
    "properties": {
        "manifest_version": {"const": "1.0"},
        "generated_utc": {"type": "string", "format": "date-time"},
        "study": {
            "type": "object",
            "required": ["study_id", "title", "study_type", "question"],
            "properties": {
                "study_id": {"type": "string", "minLength": 1},
                "title": {"type": "string", "minLength": 1},
                "study_type": {"type": "string", "minLength": 1},
                "question": {"type": "string", "minLength": 1},
                "phenomena": {"type": "array", "items": {"type": "string"}},
                "limitations": {"type": "array", "items": {"type": "string"}},
            },
        },
        "aoi": {
            "type": "object",
            "required": ["geojson", "bounds_4326", "crs", "analysis_crs", "area_km2"],
            "properties": {
                "geojson": {"type": "object"},
                "bounds_4326": {"type": "array", "minItems": 4, "maxItems": 4},
                "crs": {"const": "EPSG:4326"},
                "analysis_crs": {"type": "string", "minLength": 4},
                "area_km2": {"type": "number", "exclusiveMinimum": 0},
                "grid": {
                    "type": "object",
                    "required": ["resolution_m", "transform", "width", "height"],
                    "properties": {
                        "resolution_m": {"type": "number", "exclusiveMinimum": 0},
                        "transform": {"type": "array", "minItems": 6, "maxItems": 6},
                        "width": {"type": "integer", "exclusiveMinimum": 0},
                        "height": {"type": "integer", "exclusiveMinimum": 0},
                    },
                },
            },
        },
        "catalog": {
            "type": "object",
            "required": ["endpoint", "collection", "provider", "license"],
            "properties": {
                "endpoint": {"type": "string", "format": "uri"},
                "collection": {"type": "string", "minLength": 1},
                "provider": {"type": "string", "minLength": 1},
                "license": {"type": "string", "minLength": 1},
            },
        },
        "periods": {
            "type": "array",
            "minItems": 2,
            "items": {
                "type": "object",
                "required": [
                    "period_id",
                    "scene",
                    "acquisition_date",
                    "valid_fraction",
                    "mask_policy",
                    "outputs",
                ],
                "properties": {
                    "period_id": {"enum": ["earlier", "later"]},
                    "acquisition_date": {"type": "string", "minLength": 10},
                    "valid_fraction": {"type": "number", "minimum": 0, "maximum": 1},
                    "mask_policy": {"type": "object"},
                    "scene": {"type": "object"},
                    "outputs": {"type": "object"},
                },
            },
        },
        "processing": {
            "type": "object",
            "required": ["pipeline_version", "profile", "operations", "parameters"],
            "properties": {
                "pipeline_version": {"type": "string"},
                "profile": {"type": "string"},
                "operations": {"type": "array", "items": {"type": "string"}},
                "parameters": {"type": "object"},
            },
        },
        "outputs": {"type": "object", "minProperties": 1},
        "software": {"type": "object", "minProperties": 1},
        "attribution": {
            "type": "object",
            "required": ["text", "license", "access_date_utc"],
        },
        "validity": {
            "type": "object",
            "required": ["comparable_valid_fraction", "suitable_for_comparison"],
            "properties": {
                "comparable_valid_fraction": {
                    "type": "number", "minimum": 0, "maximum": 1
                },
                "suitable_for_comparison": {"type": "boolean"},
            },
        },
    },
}



class ManifestError(ValueError):
    """Raised when a manifest is structurally incomplete."""


class ManifestBuilder:
    """Accumulate provenance sections, validate once, then write."""

    def __init__(self) -> None:
        self.data: dict[str, Any] = {
            "manifest_version": "1.0",
            "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        }

    def set(self, key: str, value: Any) -> "ManifestBuilder":
        self.data[key] = value
        return self

    def update(self, values: dict[str, Any]) -> "ManifestBuilder":
        self.data.update(values)
        return self

    def validate(self) -> None:
        errors = sorted(
            jsonschema.Draft202012Validator(MANIFEST_SCHEMA).iter_errors(self.data),
            key=lambda e: list(e.path),
        )
        if errors:
            rendered = "; ".join(
                f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"
                for e in errors[:6]
            )
            raise ManifestError(f"manifest incomplete: {rendered}")

    def write(self, path: Path) -> Path:
        self.validate()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        return path


def validate_manifest(payload: dict[str, Any]) -> None:
    """Validate an already-loaded manifest dictionary."""
    jsonschema.Draft202012Validator(MANIFEST_SCHEMA).validate(payload)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def describe_output(path: Path, kind: str) -> dict[str, Any]:
    """Standard output record: portable path, size and checksum."""
    return {
        "kind": kind,
        "path": config.relative(path),
        "bytes": Path(path).stat().st_size,
        "sha256": sha256_file(path),
    }
