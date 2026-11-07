"""M2 research experiments: validated configuration, estimators, uncertainty.

The package reuses the frozen M0/M1 artefacts.  It never re-downloads imagery,
never overwrites an existing run, and reports only values computed from the
stored rasters and the content-addressed observation cache.
"""

from .config import M2Config, M2ConfigError, load_m2_config

__all__ = ["M2Config", "M2ConfigError", "load_m2_config"]
