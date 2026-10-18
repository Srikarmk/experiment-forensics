import hashlib
import json

import pytest

from forensics import cli
from forensics.data import ConfirmatoryLocked, check_confirmatory_allowed, load_upworthy
from forensics.upworthy import run_upworthy


def _plan(root, text="# plan\n"):
    (root / "ANALYSIS_PLAN.md").write_text(text)
    return hashlib.sha256(text.encode()).hexdigest()


def test_refuses_without_lock(tmp_path):
    _plan(tmp_path)
    with pytest.raises(ConfirmatoryLocked):
        check_confirmatory_allowed(tmp_path)


def test_loader_refuses_before_opening_file(tmp_path):
    _plan(tmp_path)
    # The path does not exist: the guard must fire before any read is attempted.
    with pytest.raises(ConfirmatoryLocked):
        load_upworthy("confirmatory", root=tmp_path, path=tmp_path / "does-not-exist.csv")


def test_cli_refuses_without_lock(tmp_path, monkeypatch):
    _plan(tmp_path)
    called = []
    monkeypatch.setattr("forensics.upworthy.run_upworthy", lambda *a, **k: called.append(1))
    with pytest.raises(ConfirmatoryLocked):
        cli.run("confirmatory", root=tmp_path)
    assert not called


def test_cli_main_exit_code(tmp_path):
    _plan(tmp_path)
    assert cli.main(["run", "--release", "confirmatory"], root=tmp_path) == 2


def test_refuses_when_digest_does_not_match(tmp_path):
    _plan(tmp_path)
    (tmp_path / "ANALYSIS_PLAN.lock").write_text("0" * 64 + "  ANALYSIS_PLAN.md\n")
    with pytest.raises(ConfirmatoryLocked):
        check_confirmatory_allowed(tmp_path)


def test_allows_with_lock(tmp_path):
    digest = _plan(tmp_path)
    (tmp_path / "ANALYSIS_PLAN.lock").write_text(f"{digest}  ANALYSIS_PLAN.md\n")
    check_confirmatory_allowed(tmp_path)
    (tmp_path / "ANALYSIS_PLAN.lock").write_text("frozen\n")
    check_confirmatory_allowed(tmp_path)


def test_confirmatory_run_end_to_end_on_synthetic(tmp_path, upworthy_csv):
    """The one-command confirmatory path works once the lock exists (synthetic data only)."""
    from tests.conftest import make_upworthy

    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)
    make_upworthy(n_tests=150, seed=1).to_csv(raw / "upworthy-archive-exploratory-packages-03.12.2020.csv",
                                              index=False)
    make_upworthy(n_tests=200, seed=2).to_csv(raw / "upworthy-archive-confirmatory-packages-03.12.2020.csv",
                                              index=False)
    up, _ = run_upworthy("exploratory", root=tmp_path, n_sims=300)
    (tmp_path / "reports").mkdir()
    (tmp_path / "reports" / "results_exploratory.json").write_text(
        json.dumps({"upworthy": up}, default=cli._json_default))
    digest = _plan(tmp_path)
    (tmp_path / "ANALYSIS_PLAN.lock").write_text(digest + "\n")
    out = cli.run("confirmatory", root=tmp_path, n_sims=300)
    text = out.read_text()
    assert "Exploratory vs confirmatory" in text
    assert (tmp_path / "reports" / "results_confirmatory.json").is_file()
