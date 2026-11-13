# Handoff: HabitatShift technical report, GitHub and Zenodo (state on 13 November 2026)

This file is kept out of git (listed in `.git/info/exclude`). Read it fully before changing anything.

## 1. Where things are

- Project folder (as last seen): `D:\Zcode project\Habitat Shift\HabitatShift`
  If the folder has moved, the repo itself moves with it. Only the path changes; all commands below are relative to the repo root.
- Git branch `main`, latest commit `ff3f3fb Update the demo GIF to the current site`.
- Git history was rewritten once (Git LFS migration). Commit hashes from before that step changed; the messages did not. Tags `m0-verified` and `m1-verified` were rewritten along with the history.
- Untracked files that must stay out of git:
  - `docs/paper/report.zip`: the Overleaf upload, not a project file.
  - `docs/paper/report/~$paper.html`: an editor lock file. Delete it.
- Remote: this local repo had no `origin` remote when last checked. The user has since published to GitHub as `AyushK60/HabitatShift` (the Zenodo record lists this URL), so check `git remote -v` before any push.
- Python virtual env: `.venv\Scripts\python.exe` in the repo root.

## 2. Report build and checks (run from repo root)

```
.venv\Scripts\python.exe scripts\build_paper.py docs\paper\report
node tools\visual\render_paper_v3.mjs docs\paper\report docs\paper\HabitatShift_Technical_Report.pdf
.venv\Scripts\python.exe -m pytest backend\tests\test_report_numbers.py backend\tests\test_paper_numbers.py
```

Other checks:
- Backend tests: `.venv\Scripts\python.exe -m pytest backend\tests` (all pass).
- ML reproducibility audit: `.venv\Scripts\python.exe verification\audit_m5_ml.py` (107 of 107 pass; it rewrites `docs\evidence\m5\audit_m5_ml_checks.json`).

Notes:
- `scripts/build_paper.py` builds the report folder and, when run with no argument, the v3 paper in `docs/paper/v3`. The v3 paper's outputs are not yet rebuilt in IEEE style.
- LaTeX (`main.tex`) has not been compiled locally. It is used in Overleaf only. Do not treat Overleaf as the final check.
- Never edit a number in `paper.md` by hand without re-running the matching audit or script. Section 7's verification table must be updated from real command output if a count changes.

## 3. What was done, in order

1. **Affiliation and co-author.** Affiliation: Andhra University. Co-author: Pragyan Kumar Singh. Added in `docs/paper/report/paper.md`, `.zenodo.json` and `CITATION.cff` (names and affiliation only). His email is deliberately NOT in any file. Ayush Khanal is the author on the v3 draft (`docs/paper/v3`), which is still single-author with a placeholder affiliation. The user decided not to add Pragyan to v3.
2. **IEEE references.** Citations numbered in order of first use. The HTML list and the LaTeX bibliography (IEEEtran with `cite`) follow IEEE form. Fixes made: in-text `[6], [7]`; dataset entry; arXiv entries as `arXiv:ID, year`; Vovk book shows "New York: Springer, 2005" (city taken from catalogue search results). Long author lists use "and others" in `refs.bib` so both outputs show "et al.".
3. **Layout fixes for Overleaf.** LaTeX tables wrapped in `resizebox` to the text width. The user reported the Overleaf output previously ran past the margins. Not yet confirmed by the user after the latest upload.
4. **Commits so far:** `b1f328c` (co-author and IEEE), `838599b` (table width, bib et al.), `ff3f3fb` (demo GIF). Commit messages have no AI or co-author lines, following the user's rule.
5. **Large files.** The two `model.joblib` files over 50 MB (one at 122 MB, over GitHub's 100 MB limit) were moved to Git LFS across all branches. All 18 `.joblib` files are now LFS-tracked (`.gitattributes` committed). The user chose to keep all 18. Free GitHub LFS limits are about 1 GB storage and 1 GB bandwidth a month (please check the current limits); one clone downloads about 800 MB.
6. **Demo GIF.** The old `docs/screenshots/demo.gif` (12 Nov) was out of date. A new one was recorded from a rebuilt frontend using `tools/visual/capture_demo_gif_frames.mjs` at localhost:8098. 31 frames, 960×570, 800 ms per frame, 3.2 MB. Mid-frame checked against the current UI.
7. **GitHub.** The user published the repo with GitHub Desktop (repo name `HabitatShift`, owner `AyushK60`).
8. **Zenodo.** Record 24201720 is published: version v3.0.0, software, MIT, authors Khanal, Ayush and Singh, Pragyan Kumar, both at Andhra University.
   - Version DOI: **10.5281/zenodo.24201720** (use this one in the report).
   - Concept DOI (all versions): **10.5281/zenodo.24201719**.
   - The zip is 153.6 MB. Not yet checked whether it contains the real models or LFS pointer files. Check by downloading it, if needed, before writing about it.

## 4. Open items, in order

1. **Add the DOI** (approved by the user in principle, not yet done):
   - `docs/paper/report/paper.md`: the Section 7 "Reproducing" paragraph and the title block (or "Status" line if that is where it belongs).
   - `CITATION.cff`: add `doi: 10.5281/zenodo.24201720` (and optionally a `version: 3.0.0` check, already present).
   - `README.md`: add the DOI badge or a line with the DOI.
   - Then rebuild the report and PDF, run both number tests, and show the user the diff before committing.
2. **Check the LFS content of the Zenodo zip.** Say what it contains. If it has pointers only, add a README note: models are on GitHub via LFS (`git lfs pull`).
3. **Commit** the DOI change after the user approves. Do not push unless asked. Commit message: no AI, Claude or co-author lines.
4. **Optional: separate Zenodo record for the report PDF.** Upload `docs/paper/HabitatShift_Technical_Report.pdf` as a publication (technical report), CC BY 4.0, related to the software DOI. Do this only after the friend has checked the references, because a published Zenodo record can't be edited, only versioned.
5. **Friend's reference check:** still pending. Items to check: U-Net page range 234–241 (not confirmed from a source); Vovk book city; Otsu, Breiman and Angelopoulos details; DOIs for SSL4EO-S12 and Zanaga. Any change means rebuild, re-run tests, then commit.
6. **Optional: EarthArXiv** (second home for the PDF). Check the current submission form first, because fields change.

## 5. Rules to keep

- Do not commit, push, tag, publish or upload unless the user says so. Uploads publish under the user's account; the user does the final click.
- No AI, Claude, "generated" or co-author lines in files, commits, release notes or metadata.
- No email addresses in published files. The user's git email is `ayush.khanal2060@gmail.com`; the account email is different. Use only the name Ayush Khanal and Pragyan Kumar Singh.
- Do not invent references, DOIs or page numbers. Look each one up (Crossref, arXiv, publisher page) and say what was checked.
- Never kill all `python.exe` processes. Stop only a specific PID after checking which process it is.
- If a number changes, update the verification table in Section 7 by hand from the real command output, then re-run the tests.

## 6. Who is who

- Ayush Khanal: author, owner of the repo and Zenodo account (`AyushK60`).
- Pragyan Kumar Singh: co-author of the technical report (Andhra University).
- The user's friend checking references: not named in files.
