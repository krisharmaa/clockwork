# Group 14: contribution evidence

Names, roll numbers, GitHub handles and the Group Leader role were supplied by
the group. The descriptions below are based on the complete local Git history
through `343b260521a66906b6a63bbc9ad80a4c856b9e63`, GitHub commit metadata and
the five merged pull requests. They summarize recorded submissions and changed
files; they do not establish exclusive personal source authorship, hours worked,
unrecorded reviews or a complete eight-week participation history.

## Akshat Tikaria — 241070005 — akshattikaria — Group Leader

Published and integrated the core optimization and validated memetic releases,
experiments, tests and academic deliverables; published exact-front reporting
and final merged-code audit cleanup.

- [9947d9d](https://github.com/akshattikaria/Optimization-Project-OT-BY-AKSHAT-MANAV-KRISH-PARTH/commit/9947d9ded50c762c5b8478ed29d612b508996cd6): bulk publication of the core project, including `src/timetable/model.py`, `evaluation.py`, `greedy.py`, `nsga2.py`, datasets, tests and mathematical documentation.
- [6e94681](https://github.com/akshattikaria/Optimization-Project-OT-BY-AKSHAT-MANAV-KRISH-PARTH/commit/6e9468183d22569939ee6aa8c51811ad2297680d): publication of `memetic.py`, `feasible.py`, `faculty_search.py`, paired comparison infrastructure, study records and report/presentation artifacts.
- [14888c6](https://github.com/akshattikaria/Optimization-Project-OT-BY-AKSHAT-MANAV-KRISH-PARTH/commit/14888c6): exact-arithmetic reporting in `experiments/exact_fronts.py`, precision tests and audit documentation.
- [343b260](https://github.com/akshattikaria/Optimization-Project-OT-BY-AKSHAT-MANAV-KRISH-PARTH/commit/343b260521a66906b6a63bbc9ad80a4c856b9e63): merged-project cleanup across API, algorithms and frontend, regression tests and saved audit evidence.

These commits use the Git author label `akshat`. The repository owner's merge
of PR #5 is recorded as `akshattikaria`. Bulk publication is described as
publication/integration rather than proof that all included files were written
individually by the committer.

## Sharma Krish Amit — 241070036 — krisharmaa

Integrated the Clockwork frontend/API, accounts and calendar; added disruption
re-optimization, website workflows and related tests.

- Merged [PR #1](https://github.com/akshattikaria/Optimization-Project-OT-BY-AKSHAT-MANAV-KRISH-PARTH/pull/1), substantive commit [9987c06](https://github.com/akshattikaria/Optimization-Project-OT-BY-AKSHAT-MANAV-KRISH-PARTH/commit/9987c06f4bc0b5ef841fc571c3d8d2eebf449a5d): `api/server.py`, `bridge.py`, `optimizer.py`, campus routes/calendar, `frontend/`, web tests and `experiments/web_integration_check.py`.
- Merged [PR #2](https://github.com/akshattikaria/Optimization-Project-OT-BY-AKSHAT-MANAV-KRISH-PARTH/pull/2), commit [d7acb20](https://github.com/akshattikaria/Optimization-Project-OT-BY-AKSHAT-MANAV-KRISH-PARTH/commit/d7acb20392f01185c9be5e6f38d0fe647b863431): `src/timetable/disruption.py`, CLI support, disruption study script and `tests/test_disruption.py`.
- Merged [PR #3](https://github.com/akshattikaria/Optimization-Project-OT-BY-AKSHAT-MANAV-KRISH-PARTH/pull/3), commit [4f32a71](https://github.com/akshattikaria/Optimization-Project-OT-BY-AKSHAT-MANAV-KRISH-PARTH/commit/4f32a716882db01fde3e4a66e991d6aea0fae76c): `api/disruptions.py`, `frontend/src/pages/Disruptions.tsx` and `tests/test_web_disruptions.py`.

Git author labels `krish` and `Krish Sharma` resolve to the GitHub account
`krisharmaa` in the commit/PR metadata. The Clockwork integration commit includes
an assistant co-author trailer; this summary does not claim exclusive authorship.

## Rajesh Manavaditya — 241070040 — Manavaditya-rajesh

Added supplementary MOEA/D, AMOSA-inspired annealing, MCDM, CP-SAT
epsilon-constraint runs and the five-method comparison/visualization.

- Merged [PR #4](https://github.com/akshattikaria/Optimization-Project-OT-BY-AKSHAT-MANAV-KRISH-PARTH/pull/4), substantive commit [cf0110d](https://github.com/akshattikaria/Optimization-Project-OT-BY-AKSHAT-MANAV-KRISH-PARTH/commit/cf0110dce79d8838a7bd9346177351c26be2f4f7).
- Representative changes: `src/timetable/moead.py`, `amosa.py`, `mcdm.py`, `exact.py`, `cli.py`, `experiments/compare_all_methods.py`, frontend comparison views and `tests/test_new_optimization_methods.py`.
- `cdbb02d` merges upstream changes into the PR branch, despite repeating the feature title; it is not counted as a second independent implementation. The PR merge is `82e28e8`.

Later commits correct and extend these methods. Their current implementation
and historical measurements should be described with the provenance limits in
[advanced methods](ot_advanced_methods.md).

## Paarth Maharshi — 241070050 — PaarthMaharshi

Added exact gaps/room references, AHP and sensitivity analysis, supplementary
study scripts/results; corrected measured-only website results, optional
comparisons and documentation.

- Merged [PR #5](https://github.com/akshattikaria/Optimization-Project-OT-BY-AKSHAT-MANAV-KRISH-PARTH/pull/5), merge commit `7b43c07`.
- [7833e17](https://github.com/akshattikaria/Optimization-Project-OT-BY-AKSHAT-MANAV-KRISH-PARTH/commit/7833e17): exact two-objective reference, AHP/TOPSIS sensitivity and paired-study support in `exact.py`, `mcdm.py`, `cli.py` and `experiments/moead_paired_study.py`.
- [c088bcb](https://github.com/akshattikaria/Optimization-Project-OT-BY-AKSHAT-MANAV-KRISH-PARTH/commit/c088bcb6a8fcc1cbb69066f0253dc687b4fc6752) and [51664e9](https://github.com/akshattikaria/Optimization-Project-OT-BY-AKSHAT-MANAV-KRISH-PARTH/commit/51664e979c808d5b9b575aa4b22ca2d66392b135): supplementary study scripts/records, including `results/moead_paired/` and `results/exact_gap/`, and weighted-sum sweep corrections.
- [252c12a](https://github.com/akshattikaria/Optimization-Project-OT-BY-AKSHAT-MANAV-KRISH-PARTH/commit/252c12a) and [2939788](https://github.com/akshattikaria/Optimization-Project-OT-BY-AKSHAT-MANAV-KRISH-PARTH/commit/2939788): measured-only website values and optional Advanced benchmark.
- [f594524](https://github.com/akshattikaria/Optimization-Project-OT-BY-AKSHAT-MANAV-KRISH-PARTH/commit/f594524acc7b066d75defeb435004e45efef0fab) and [471b6a6](https://github.com/akshattikaria/Optimization-Project-OT-BY-AKSHAT-MANAV-KRISH-PARTH/commit/471b6a6): supplementary report/slide sources and pre-freeze audit record. The commit message explicitly says the binary report/slides were not rebuilt in that commit; subsequent audit work rebuilt them.

## Verification and review

GitHub PR metadata confirms authors `krisharmaa` (#1–3),
`Manavaditya-rajesh` (#4) and `PaarthMaharshi` (#5). All five PRs are merged,
and their head/merge commits are present in the local main history.
Representative file claims were checked against the corresponding commit diffs.
No work dates or weekly entries have been invented. The group may refine the
wording using additional genuine evidence before submission.

To inspect the same records locally:

```bash
git log --format='%h | %an | %s' 343b260
git show --stat 9947d9d 6e94681 9987c06 d7acb20 4f32a71 cf0110d 7833e17 51664e9
```
