"""Command line entry point: `forensics run --release exploratory|confirmatory`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from . import config, plots
from .data import PROJECT_ROOT, ConfirmatoryLocked, check_confirmatory_allowed
from .report import confirmatory_markdown, exploratory_markdown


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return str(o)


def _write_json(obj, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=_json_default) + "\n")


def upworthy_figures(res, frames, fig_dir: Path, prefix: str = ""):
    plots.peeking_curve(res["peeking"]["aa"], fig_dir / f"{prefix}peeking_false_positive.png")
    plots.effect_distribution(frames["comp"], fig_dir / f"{prefix}effect_distribution.png")
    plots.mde_plot(frames["tests"], res["power"]["typical_true_abs_effect_pp_grid"], fig_dir / f"{prefix}power_mde.png")
    plots.shrinkage_plot(frames["comp"], frames["sig"], res["winners"]["examples"], fig_dir / f"{prefix}shrinkage.png")


def run(release: str, root: Path = PROJECT_ROOT, n_sims: int = config.N_SIMS, data_path: Path | None = None) -> Path:
    root = Path(root)
    reports = root / "reports"
    fig_dir = reports / "figures"
    if release == "confirmatory":
        # Checked here and again inside the loader, before any file is opened.
        check_confirmatory_allowed(root)
        expl_path = reports / "results_exploratory.json"
        if not expl_path.is_file():
            raise SystemExit(f"{expl_path} is missing; run the exploratory release first.")
    from .upworthy import run_upworthy

    up, frames = run_upworthy(release, root=root, path=data_path, n_sims=n_sims)
    if release == "exploratory":
        from .hillstrom import run_hillstrom

        hs, hframes = run_hillstrom(root)
        _write_json({"upworthy": up, "hillstrom": hs}, reports / "results_exploratory.json")
        upworthy_figures(up, frames, fig_dir)
        plots.hillstrom_ci(hframes["estimates"], fig_dir / "hillstrom_ci.png")
        plots.subgroup_forest(hframes["subgroups"], "spend", fig_dir / "subgroup_forest_spend.png")
        plots.subgroup_forest(hframes["subgroups"], "visit", fig_dir / "subgroup_forest_visit.png")
        out = reports / "exploratory.md"
        out.write_text(exploratory_markdown(up, hs))
    else:
        expl = json.loads((reports / "results_exploratory.json").read_text())["upworthy"]
        _write_json({"upworthy": up}, reports / "results_confirmatory.json")
        upworthy_figures(up, frames, fig_dir, prefix="confirmatory_")
        out = reports / "confirmatory.md"
        out.write_text(confirmatory_markdown(json.loads(json.dumps(up, default=_json_default)), expl))
    return out


def main(argv=None, root: Path = PROJECT_ROOT):
    ap = argparse.ArgumentParser(prog="forensics", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run the analyses on one Upworthy release (and Hillstrom for exploratory)")
    r.add_argument("--release", choices=["exploratory", "confirmatory"], default="exploratory")
    r.add_argument("--n-sims", type=int, default=config.N_SIMS)
    args = ap.parse_args(argv)
    try:
        out = run(args.release, root=root, n_sims=args.n_sims)
    except ConfirmatoryLocked as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
