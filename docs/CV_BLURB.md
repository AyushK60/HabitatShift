# CV and portfolio blurbs

Every claim maps to a recorded artifact (see `docs/archive/FINAL_AUDIT.md`).

**One-liner**
Built HabitatShift, a reproducible Sentinel-2 change-analysis platform
(FastAPI, React/MapLibre, scikit-learn) with an independent audit layer that
re-derives its results from live source data.

**CV bullets (pick 3-4)**
- Designed and built a six-study Sentinel-2 change-detection platform with a FastAPI backend and React/TypeScript/MapLibre frontend, including swipe comparison, pixel probe, and an offline static showcase.
- Wrote an independent audit that imports no production code and verifies 4,111 checks against live STAC records and COG pixels; it found and fixed a provenance defect (30 stale output checksums).
- Demonstrated reproducibility: a fresh virtual environment regenerated a study from source data into byte-identical GeoTIFFs.
- Trained label-gated Random Forests with 1 km spatial block cross-validation, reported as agreement with ESA WorldCover and withheld where class support was too small.
- Ran sensitivity analyses (minimum mapping unit, block-bootstrap block size, feature-group withholding) and kept five uncertainty categories separate instead of one score.
- Maintained 404 automated tests, 4 browser suites, and a clean `pip-audit` (upgraded 89 advisories to zero).

**Short paragraph (cover letter / statement)**
HabitatShift started from a question I care about, how landscapes in South Asia
change, and became an exercise in scientific discipline. The platform measures
candidate spectral change between two dates, shows its uncertainty, and refuses
to claim more than the data support: for example it reports that the Western
Ghats study is essentially stable rather than inventing deforestation. I built
the backend, the interface, and an audit layer that reproduces the results
independently from source data.

**Interview points**
- Why agreement with WorldCover, not accuracy: the reference is itself a model.
- Why Coringa mangroves have no supervised run: two authoritative inventories disagree.
- The radiometry offset trap found in M0 (double-applied BOA offset) and how it was resolved with evidence.
- The checksum defect the audit caught in the project's own earlier work.

*Edit before use: replace "I" statements with your real role and add your own
motivation; keep the numbers as recorded.*
