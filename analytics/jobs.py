"""Nightly batch orchestration: DB -> layers A-D (pure funcs) -> results tables.

Thin I/O wrapper per agents.md §6 — the math lives in layer_*.py.
TODO(P2.x): wire each step as data accumulates; each writes validation_runs.
"""
from __future__ import annotations

import argparse


def run_once() -> None:
    print("batch: layer A (polar) — TODO(P2.6): needs readings+weather history")
    print("batch: layer B (surfaces+LOOCV) — TODO(P2.2/P2.4)")
    print("batch: layer C (NMF) — TODO(P2.10): needs weeks of multi-pollutant history")
    print("batch: layer D (context) — TODO(P2.13): needs static GIS loaded")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.parse_args()
    run_once()


if __name__ == "__main__":
    main()
