# Merged-project audit evidence

These are captured verification records for the final cleanup of merged revision
`7b43c07ae1da7d649e4f1477d6f087241b6eb5b6`, dated 14 November 2026.
See the [audit report](../../docs/merged_final_audit.md) for fixes, scope,
reproduction commands and manual submission requirements.

- [summary.json](summary.json): observed outcomes and explicit limitations.
- [release_pytest.txt](release_pytest.txt): complete corrected suite, 417 passed.
- [baseline_pytest.txt](baseline_pytest.txt): untouched merged revision, 267 passed.
- [checked_sources.json](checked_sources.json): SHA-256 hashes of the checked
  source, tests, configurations and dependency files.
- [cli_checks.json](cli_checks.json): all 55 CLI invocations and exit codes.
- [web_checks.json](web_checks.json): all 61 live HTTP checks.
- [browser_checks.json](browser_checks.json): 13 real browser workflows and
  absence of uncaught page exceptions; failure/race output is saved separately.
- [enhancement_reverification.json](enhancement_reverification.json): current
  independent checks of the historical held-out records, including live source
  drift. The original historical verification record is preserved.
- [dataset_replay.json](dataset_replay.json): byte-identical regeneration proof
  for 14 stored instances and 14 certificates.
- [artifact_checks.json](artifact_checks.json): report/slides, hashes, links and
  repository hygiene checks.

The remaining text files capture installation, build, execution, plotting and
smoke-check outputs. `*_smoke_summary.json` files describe **quick execution
checks**, not a new replicated performance study. Measurements of the full
historical benchmark campaigns were revalidated, not rerun or replaced. Local
paths/ports in logs identify disposable audit environments and databases.
