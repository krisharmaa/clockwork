"""Historical measurements keep their own source identity after unrelated merges."""
from hashlib import sha256
import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("saved_source_verifier", Path(__file__).parents[1] / "experiments/verify_enhancement.py")
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


def source_tree(tmp_path):
    root, study = tmp_path / "repo", tmp_path / "study"
    files = {name: f"recorded {name}".encode() for name in ("model.py", "evaluation.py", "metrics.py", "exact.py", "cli.py")}
    for name, content in files.items():
        for folder in (root / "src/timetable", study / "source_snapshot"):
            folder.mkdir(parents=True, exist_ok=True)
            (folder / name).write_bytes(content)
    return root, study, {name: sha256(content).hexdigest() for name, content in files.items()}


def test_unrelated_extensions_are_reported_without_rewriting_measurement_identity(tmp_path):
    root, study, files = source_tree(tmp_path)
    (root / "src/timetable/exact.py").write_text("later exact reference")
    result = verifier.verify_recorded_sources(root, study, files)
    assert result["source_snapshot_hashes_valid"]
    assert result["validation_code_matches_snapshot"]
    assert not result["source_snapshot_matches_current"]
    assert result["current_source_differences"] == ["exact.py"]


@pytest.mark.parametrize("name", ["model.py", "evaluation.py", "metrics.py"])
def test_changed_validation_implementation_cannot_claim_historical_revalidation(tmp_path, name):
    root, study, files = source_tree(tmp_path)
    (root / "src/timetable" / name).write_text("different validation")
    with pytest.raises(ValueError, match="recorded revision"):
        verifier.verify_recorded_sources(root, study, files)


def test_corrupted_measured_source_snapshot_is_rejected(tmp_path):
    root, study, files = source_tree(tmp_path)
    (study / "source_snapshot/cli.py").write_text("corrupted measured source")
    with pytest.raises(ValueError, match="corrupted"):
        verifier.verify_recorded_sources(root, study, files)
