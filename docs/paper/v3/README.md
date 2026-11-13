# Version 3 paper (draft)

`paper.md` is the single source. `scripts/build_paper.py` turns it into `main.tex` (upload this folder to Overleaf with
`refs.bib` and `figures/`) and `paper.html`; `node tools/visual/render_paper_v3.mjs` makes
`HabitatShift_V3_paper_preview.pdf` for reading without LaTeX installed. Figures come from
`scripts/make_paper_figures.py`, which reads only recorded outputs. `backend/tests/test_paper_numbers.py` checks that
the numbers in the text match those outputs.

Rebuild after any change to `paper.md`:

```powershell
.venv\Scripts\python.exe scripts\make_paper_figures.py
.venv\Scripts\python.exe scripts\build_paper.py
cd tools\visual; node render_paper_v3.mjs
```

## Before this goes anywhere public

- [ ] Fill in the affiliation line in `paper.md`.
- [ ] Check every entry in `refs.bib` against the publisher or arXiv page (they were written from memory: authors,
      page numbers, arXiv ids). Add any related work you want to cite; the introduction cites only what it needs.
- [ ] Compile `main.tex` on Overleaf once and fix any layout problem (it has not been compiled on this machine).
- [ ] Re-read the limitations section as a sceptical reviewer would; the strongest objections are listed there.
- [ ] Decide the venue. Deadlines and formats change every year, so check the current call: ML for Remote Sensing and
      Climate Change AI workshops, or an IGARSS student paper. Do not rely on any date written in the plan.
- [ ] Preprint: EarthArXiv needs no endorsement. arXiv may require an endorser for a first submission in a category.
- [ ] Your supervisor or a senior person should read it before submission.

## Claims the paper does not make

It does not claim foundation models are bad: only that frozen embeddings did not beat a simple baseline in these two
fields with this reference data. It does not claim accuracy: every reference is another model's output.
