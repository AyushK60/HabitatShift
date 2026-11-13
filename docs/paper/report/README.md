# Technical report

`paper.md` is the single source. `scripts/build_paper.py docs/paper/report` turns it into `main.tex` (upload this folder to
Overleaf with `refs.bib` and `figures/`) and `paper.html`; the PDF is made from the HTML with:

```powershell
.venv\Scripts\python.exe scripts\build_paper.py docs\paper\report
node tools\visual\render_paper_v3.mjs docs\paper\report docs\paper\HabitatShift_Technical_Report.pdf
```

`backend/tests/test_report_numbers.py` fails if a table or claim in `paper.md` disagrees with the recorded outputs, so
re-run the audits and the tests before rebuilding. The verification table in Section 7 was produced by running each
audit script (`verification/`) and `pytest`; update it by hand from those runs when they change.

Before it goes anywhere public:

- [ ] Fill in the `Affiliation:` line in `paper.md` (left empty on purpose).
- [ ] Check every entry in `refs.bib` against the publisher or arXiv page (written from memory).
- [ ] After the Zenodo release, add the DOI to `paper.md` and rebuild.
