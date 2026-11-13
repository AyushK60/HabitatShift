# CV and portfolio blurbs

## Version 3 (research project)

**One-liner**
HabitatShift v3: a noise-calibrated test of whether geospatial foundation models (Prithvi-EO-2.0, SSL4EO) detect surface
change better than spectral indices, on forest loss and 30 Nepal glacial lakes, with a trained radar U-Net and conformal
uncertainty. Paper draft in `docs/paper/v3/`.

**CV bullets (every number is in `docs/V3_RESULTS.md`)**
- Designed a change score in units of scene-to-scene noise that works for any feature vector, and a pre-specified
  evaluation (average precision with spatial block-bootstrap intervals, plus a placebo test) comparing two foundation
  models, six raw bands, five spectral indices and a signed NDVI baseline against Hansen forest loss and Sentinel-1 water change.
- Found and reported a negative result: no foundation model beat the signed NDVI baseline on forest loss (AP 0.69 against
  0.72 in Bastar; 0.56 against 0.76 in Odisha), and at glacial lakes Prithvi and raw bands tied (0.75 and 0.76 against 0.57 for MNDWI).
- Built a 30-lake radar and optical training set (3,227 pairs from Sentinel-1 RTC and Sentinel-2) and trained a
  1.9M-weight U-Net on weak optical labels: IoU 0.70 +/- 0.03 on unseen lakes against 0.55 for a radar threshold (3 seeds).
- Checked its conformal area intervals by 5-fold cross-validation over lakes: 87% coverage at a 90% target, with two
  lakes at 0%, and reported that the guarantee holds on average but not per lake.
- Built a research website with a guided tour, plain-language and technical explanations of every graph, and a
  real-data animation of Imja Tsho growing between 2018 and 2024.

**Short paragraph (statement of purpose)**
My project asked a simple question honestly: do large pretrained satellite models detect real change better than a
simple vegetation index once you account for ordinary noise between images? In two forest areas they did not, and at
glacial lakes they matched plain reflectance. I built the evaluation so the answer could have gone the other way, kept
the negative result, and measured how far my own radar model's error bars can be trusted: on average well, for a few
lakes not at all. I want to continue this work on uncertainty in remote sensing.

**Interview points**
- Why the change score divides by noise, and what "about 1 if nothing changed" means.
- Why a placebo test with no reference is useful and why low false alarms are not evidence of detection skill.
- Why the lake result rests on one changing lake and what that does to the intervals.
- Why the radar model and the radar threshold disagree at Imja Tsho (the optical label bias) and what would settle it.
- Conformal coverage is marginal, not per lake; what a per-lake guarantee would need.

*Edit before use: replace first-person claims with your real role and motivation. Do not state results that are not
in `docs/V3_RESULTS.md`.*

---

## Version 2 (earlier work)

Every claim maps to a recorded artifact (see `docs/archive/FINAL_AUDIT.md`).

**One-liner**
Built HabitatShift, a reproducible Sentinel-2 change-analysis platform
(FastAPI, React/MapLibre, scikit-learn) with an independent audit layer that
re-derives its results from live source data.

**CV bullets (pick 3-4)**
- Designed and built a six-study Sentinel-2 change-detection platform with a FastAPI backend and React/TypeScript/MapLibre frontend, including swipe comparison, pixel probe, and an offline static showcase.
- Wrote an independent audit that imports no production code and verifies 4,111 checks against live STAC records and COG pixels; it found and fixed a provenance defect (30 stale output checksums).
- Demonstrated reproducibility: a fresh virtual environment regenerated a study from source data into byte-identical GeoTIFFs.
- Trained Random Forests (only where reference labels were usable) with 1 km spatial block cross-validation, reported as agreement with ESA WorldCover and withheld where class support was too small.
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
- The radiometry offset trap found early on (double-applied BOA offset) and how it was resolved with evidence.
- The checksum defect the audit caught in the project's own earlier work.

*Edit before use: replace "I" statements with your real role and add your own
motivation; keep the numbers as recorded.*
