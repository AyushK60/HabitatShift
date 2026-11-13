# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack
Existing: React + Vite + TypeScript in `frontend/`, static data bundles in `frontend/public/` and `studies/`, FastAPI backend optional (the site also runs as a static showcase). Charting library may be added (confirmed by the owner).

## Users
Primary: the owner (an undergraduate computer science student in Nepal) presenting the project live to a professor, and later to admissions committees reading it unaided. Secondary: non-technical viewers who need a plain-language path, and technical reviewers (remote sensing / ML) who need the method, noise estimates and caveats. (Confirmed in conversation.)

## Product Purpose
HabitatShift detects surface change in satellite images and says honestly whether a change is real or within scene-to-scene noise. Version 2: noise-aware change test on Sentinel-2, Hansen forest-loss validation, time series, custom-area runs. Version 3 research question: can geospatial foundation-model embeddings detect real change more reliably than spectral indices once both are judged against the same noise, and does it hold across fields? Flagship: Sentinel-1 radar time series for 30 Nepal glacial lakes, plus a small trained U-Net with conformal area intervals. Success: a professor can follow the story without help in a few minutes and can find the evidence behind every claim.

## Positioning
Reports agreement, not accuracy; states plainly when a result is not distinguishable from noise, including negative results (no foundation model beat a signed NDVI baseline on forest loss). Every number shows its uncertainty.

## Operating Context
Used in a live meeting on a laptop projector or shared screen, and as a static site (GitHub Pages deploy later, not yet pushed). Data is pre-computed; nothing needs a login.

## Capabilities and Constraints
Existing pages: Explore, Experiments, Workstation, Methods, Scene check, Glacial lakes. All existing functionality and data must stay. Static data under `frontend/public/` (including `lakes/lakes.json`, extended with a radar U-Net series). Terminology to keep consistent: "agreement with a reference, not accuracy"; "noise test"; "foundation model"; "conformal interval".

## Brand Commitments
No mention that an AI assistant helped build the project (owner's instruction). No invented numbers, customers or claims. Owner's name: Ayush Khanal.

## Evidence on Hand
Study bundles under `studies/` and `frontend/public/`; V3 results in `docs/V3_RESULTS.md`; lake data `frontend/public/lakes/lakes.json`. No testimonials or external benchmarks exist; none may be invented.

## Product Principles
1. Plain words first, method on demand: every chart has a one-line takeaway for non-experts and an expandable technical note.
2. Uncertainty is always drawn, never hidden.
3. Negative and partial results are shown as clearly as positive ones.
4. One obvious next step on every screen; nothing buried.
5. A viewer can follow the story without being told where to click.

## Accessibility & Inclusion
Readable on a projector (high contrast, large type for key numbers); keyboard operable; respects reduced motion. Audience includes non-native English readers: short sentences.

<!-- Inferred from the owner's brief and earlier conversation; the owner was asked about story, charting library and git handling, and otherwise delegated decisions. -->
