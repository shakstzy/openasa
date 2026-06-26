# openasa — open automated semen analysis

A smartphone-microscope pipeline for at-home **sperm concentration + motility**
screening. Point a phone camera through a cheap clip-on lens at a fixed-depth
counting chamber, take a short video, and get a WHO-style screening report:
concentration (million/mL), total motility %, and progressive motility %, each
flagged against the WHO 6th-edition reference limits.

This repo is the **software + reference hardware** for that system. It is a
screening aid, **not a diagnostic device** (see `docs/REGULATORY.md`).

## What's here

| Path | What |
|------|------|
| `openasa/casa.py` | CASA kinematics engine (VCL/VAP/VSL/LIN/STR/WOB/ALH/BCF + motility grading). Pure numpy, fully unit-tested. |
| `openasa/concentration.py` | Counting-chamber math: cell count in a known volume → million/mL. |
| `openasa/report.py` | WHO 2021 report assembly + reference-limit flags. |
| `openasa/pipeline.py` | Video → detect (YOLO) → track (ByteTrack) → CASA → report. |
| `spark/run_visem.py` | End-to-end validation on the real VISEM-Tracking dataset (runs on the DGX). |
| `tests/` | 22 tests pinning the kinematics + concentration math to analytic answers. |
| `docs/FEASIBILITY.md` | Go/no-go research synthesis (commercial, clinical, optics, CV, regulatory). |
| `docs/BUILD-PLAN.md` | Phased execution plan: what's built, what's next, who does what. |
| `docs/REGULATORY.md` | The FDA reality and the two viable go-to-market paths. |

## Status

- **Analysis core: built + verified.** `pytest tests/` → 22 passing. The
  kinematics and concentration math are validated against analytically known
  trajectories and chamber geometry.
- **Detect + track: wired** to Ultralytics YOLO + ByteTrack; validated on the
  public VISEM-Tracking sperm dataset on the DGX Spark.
- **Hardware: reference BOM specced** (sub-$20 reusable clip + ~$2–6 disposable
  chamber). Not yet a printed prototype.

## Run the tests

```bash
PYTHONPATH=. python3 -m pytest tests/ -q
```

## Analyze a video (needs a GPU host with ultralytics + a sperm detector)

```python
from openasa.casa import CasaConfig
from openasa.pipeline import PipelineConfig, analyze_video

cfg  = CasaConfig(um_per_px=0.5, fps=50)          # per-device calibration
pcfg = PipelineConfig(weights="sperm_yolo.pt", casa=cfg, chamber_depth_um=20)
report = analyze_video("sample.mp4", pcfg)
print(report.to_dict())
```

The `um_per_px` and `fps` are the only per-device calibration knobs and must be
measured once per optical setup with a stage micrometer + a known frame rate.
