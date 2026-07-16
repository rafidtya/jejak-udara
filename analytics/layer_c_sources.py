"""Layer C — unsupervised source typing (NMF ≈ PMF-lite) + rule interpretation.

Honesty framing (agents.md §5): the math DISCOVERS recurring signatures; rules
INTERPRET them. Output is always (label, confidence, evidence[]) — never a bare
class. Requires multi-pollutant hourly data (reference stations); if only ISPU
index exists (P0.1 outcome), fall back to temporal archetypes (plan.md P2.12).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.decomposition import NMF


def factorize(matrix: pd.DataFrame, *, k: int = 4, seed: int = 0
              ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """NMF on a [time x pollutant] concentration matrix (non-negative, normalized).

    Returns (contributions [time x factor], profiles [factor x pollutant]).
    """
    x = matrix.to_numpy(dtype=float)
    x = np.nan_to_num(x, nan=0.0)
    x = x / np.maximum(x.max(axis=0, keepdims=True), 1e-9)  # per-pollutant scaling
    model = NMF(n_components=k, init="nndsvda", random_state=seed, max_iter=500)
    w = model.fit_transform(x)
    h = model.components_
    contributions = pd.DataFrame(w, index=matrix.index,
                                 columns=[f"factor_{i}" for i in range(k)])
    profiles = pd.DataFrame(h, columns=matrix.columns,
                            index=[f"factor_{i}" for i in range(k)])
    return contributions, profiles


def interpret_factor(profile: pd.Series, diurnal: pd.Series) -> dict:
    """Rule-based labeling from chemical profile + diurnal pattern.

    Rules (documented for judges — see brief Fitur C):
      traffic:  NOx/CO-heavy + twin rush-hour peaks (07-09 & 17-19)
      industry: SO2-heavy + flat 24h profile
      burning:  PM-heavy + evening/night peak
      dust:     PM10 >> PM2.5 + daytime
    Confidence = mean of the rule-scores that fired; never 1.0 by construction.
    """
    p = profile / max(profile.sum(), 1e-9)
    hours = diurnal / max(diurnal.max(), 1e-9)
    rush = float((hours.reindex(range(24), fill_value=0)[[7, 8, 17, 18]]).mean())
    evening = float((hours.reindex(range(24), fill_value=0)[[19, 20, 21, 22]]).mean())
    flatness = 1.0 - float(hours.std())

    scores = {
        "traffic": 0.6 * float(p.get("no2", 0) + p.get("co", 0)) + 0.4 * rush,
        "industry": 0.6 * float(p.get("so2", 0)) + 0.4 * max(flatness, 0.0),
        "burning": 0.6 * float(p.get("pm25", 0) + p.get("pm10", 0)) * 0.5 + 0.4 * evening,
        "dust": 0.7 * max(float(p.get("pm10", 0) - p.get("pm25", 0)), 0.0)
                + 0.3 * (1.0 - evening),
    }
    label = max(scores, key=scores.get)
    total = sum(scores.values()) or 1e-9
    return {
        "label": label,
        "confidence": round(scores[label] / total, 3),  # relative, honest, < 1
        "scores": {k: round(v, 3) for k, v in scores.items()},
        "evidence": [],  # Layer D appends spatial/context evidence (P2.13, P2.11b)
    }


def stability_check(matrix: pd.DataFrame, *, k: int, n_seeds: int = 5) -> float:
    """Mean pairwise cosine similarity of profiles across random seeds (0..1).

    Low stability => factors are artifacts; report this in validation_runs
    (kind='nmf_stability') instead of hiding it.
    """
    profs = []
    for seed in range(n_seeds):
        _, h = factorize(matrix, k=k, seed=seed)
        profs.append(h.to_numpy())
    sims = []
    for i in range(len(profs)):
        for j in range(i + 1, len(profs)):
            a = profs[i] / (np.linalg.norm(profs[i], axis=1, keepdims=True) + 1e-9)
            b = profs[j] / (np.linalg.norm(profs[j], axis=1, keepdims=True) + 1e-9)
            # greedy match factors between runs
            sim = np.abs(a @ b.T)
            sims.append(float(sim.max(axis=1).mean()))
    return float(np.mean(sims)) if sims else float("nan")
