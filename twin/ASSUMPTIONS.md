# twin/ASSUMPTIONS.md — what the digital twin is and is NOT

The twin is **decision-support**, not a validated operational forecaster (agents.md §5.2).
Extend this file whenever physics is added. Every UI surface renders "estimasi/simulasi".

## Model: multi-source Gaussian plume (steady-state)

1. **Steady-state wind** per simulation step: one wind vector per source's kelurahan
   (BMKG), constant over the step. Reality: urban wind fields curve and gust.
2. **Flat terrain, no buildings.** Street canyons, recirculation, and sea breeze
   (Jakarta is coastal!) are NOT modeled.
3. **Dispersion coefficients:** Briggs urban (McElroy–Pooler) power laws by stability
   class. Stability estimated heuristically from BMKG `ws` + `tcc` (day/night) —
   ±1 class of error is normal.
4. **Non-reactive pollutant.** PM2.5 treated as inert tracer; no chemistry, no
   secondary aerosol formation (a real fraction of Jakarta PM2.5 is secondary).
5. **Source strengths are RELATIVE** (from Layer C factor contributions), scaled to
   observations by least-squares calibration (P3.2). Absolute emission rates unknown.
6. **Background term:** CAMS regional PM2.5 added uniformly (imported pollution);
   local plumes superpose on top. Linear superposition assumed.
7. **Deposition/washout:** only a crude rain washout factor from BMKG `tp` in
   what-if rain scenarios; no dry deposition.

## Validation contract

Every forecast surface is persisted, then scored against subsequent SPKU
observations (`forecast_skill`). The honest bar: **beat naive persistence**
("in 3h it'll be like now"). If we don't beat it, that goes in the paper too.
