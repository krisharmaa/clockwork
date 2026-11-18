# Final presentation

## Evaluation presentation

The **10-slide presentation for 19 November 2026** covers the problem, objectives,
feasibility-preserving memetic method, application workflow, validation, results
and final timetable. It is based on the final technical report and includes a
capture of the working Clockwork frontend.

- [Download the editable PowerPoint](OT_Project_Presentation.pptx).
- [View or download the PDF](OT_Project_Presentation.pdf).

Every PowerPoint slide contains speaker notes. The suggested talk takes 8–10
minutes, followed by a two-minute live demo described in the notes for slide 9.

## Extended research presentation

The presentation contains **23 slides: 18 main slides and 5 backups**, including *Supplementary methods and website* and *Group 14 recorded contributions*. The PPTX, PDF, `preview.png`, Markdown slides, presenter notes, evidence hashes and build checks were rebuilt together on 2026-11-14. All 23 slides have speaker notes; the visible cover roster, contribution evidence, PDF text and page bounds are checked during the build, and the rendered contact sheet was inspected.
Suggested duration: 15–18 minutes plus the optional short live demonstration.
It presents the final **mutation-only feasible memetic NSGA-II**, the completed
168-run held-out comparison, all four medium/large gains, unfavorable small
results, the competitive scalar-local ablation, mathematical guarantees, and
complete timetable trade-offs.

- [Editable PowerPoint](college_timetable_optimization.pptx) — includes speaker notes on every slide.
- [Portable PDF slides](college_timetable_optimization.pdf).
- [Complete Markdown slide source](slides.md) — slide separators and speaker comments.
- [Presenter notes](presenter_notes.md) — evidence references and speaking guidance.
- [Rendered contact sheet](preview.png).
- [Build checks](build_checks.json) and [exact evidence values/hashes](evidence.json).

The cover identifies **Group 14** with the group-supplied names, rolls and GitHub handles, marks Akshat Tikaria as **Group Leader**, and names **Professor Akhil Kulal**. The contribution backup links recorded commits and merged PRs; its notes identify relevant paths. Detailed evidence and attribution limits are in [contributions](../docs/contributions.md). Recorded submissions and integration do not establish exclusive personal authorship, hours or eight-week participation. No professor approval or approval date is claimed.

## Rebuilding

Opening the supplied PPTX/PDF requires no Python dependencies. To rebuild from
the repository root, use an environment with these optional presentation libraries:

```bash
python -m pip install -r presentation/requirements.txt
python experiments/exact_fronts.py --study enhancement_validation
python presentation/build_presentation.py
```

The build uses python-pptx, Matplotlib and Pillow. PDF conversion requires
LibreOffice (`soffice`) on PATH; previews and checks also require Poppler tools
(`pdfinfo`, `pdftotext`, `pdftoppm`). These were already installed in the cloud
environment. Their use is separate from the core optimizer requirements.
Exact rational front cleanup is mandatory before reporting: floating workload SD
pseudo-ties caused 53 dominated follow-up points to be retained in the raw
archives. The exact reporting fronts retain 3,242 points from 3,295 feasible raw
schedules; raw schedules, frozen code and measured timings remain unchanged.
See [numerical precision](../docs/numerical_precision.md).

The builder reads saved measurements and creates presentation artifacts only;
it never runs an optimizer or changes experimental records.

The supplementary backup labels the later studies exploratory: their saved scalar summaries lack complete schedule archives and source manifests, and older MOEA/D/AMOSA runs predate scalarization/cooling fixes. The primary numerical results and frozen measurements are preserved. Demo execution entries in `build_checks.json` are retained historical checks; rebuilding the deck does not repeat the demo.

The shared slide specification is in `build_presentation.py`. It produces the
editable PPTX, matching LibreOffice PDF, complete Markdown and presenter notes.
New presentation charts are derived from saved objective/count/load values;
existing anytime and timetable images are reused with source references.

## Live demonstration

Activate the project's installed Python environment, then run:

```bash
bash presentation/demo.sh
```

This generates small synthetic seed 9002, solves it with the final method using
seed 0, population 12 and 120 full evaluations, and rechecks a representative.
It writes only to ignored `work/presentation_demo/`. The demo illustrates
execution and validation; it is not a fresh benchmark or a promised small-case
win over greedy. Open `work/presentation_demo/run/timetables/normalized_compromise/grids.md`
and `work/presentation_demo/figures/normalized_compromise.png` afterward.

A saved matched example is available without running optimization:

```bash
python main.py evaluate data/enhancement_validation/medium_1010.json results/enhancement_validation/timetables/medium_1010/memetic/balanced_workload/schedule.json
```

## Viva preparation

Every member should explain offering-level teacher consistency, full-block lab
occupancy, hard constraints versus objectives, genuine workload variability,
constraint domination, NSGA-II rank/crowding/survival, fair evaluation/time
accounting, the local-search ablation, empirical versus global Pareto guarantees,
and why improved workload balance may create student/faculty gaps.
