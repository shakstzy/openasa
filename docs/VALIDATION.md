# Validation — real-data end-to-end run

Run on the DGX Spark (GB10), inside the existing `comfy-venv` (torch 2.12 cu130
+ ultralytics 8.4 + cv2 4.13). Script: `spark/run_visem.py`. Voice-LLM and
homecoming frame were live throughout; GPU peaked ~4 GB of 128 GB unified, load
stayed ~0 — no contention.

## 1. Detector (YOLO11n on VISEM-Tracking)

Trained 8 epochs on the public VISEM-Tracking sperm dataset (656k labeled
boxes). Final validation metrics:

| Metric | Value |
|--------|-------|
| Precision | 0.980 |
| Recall | 0.963 |
| mAP50 | 0.987 |
| mAP50-95 | 0.833 |
| Val images / instances | 1,470 / 56,568 |

> Caveat: this demo run used a single discovered split for train+val (overlap),
> so mAP is optimistic — it proves the detector trains and detects sperm
> reliably, not a clean generalization number. Build-plan item 1.6 swaps in
> VISEM-Tracking's own Train/Test split for an honest mAP. (The legacy YOLOv5
> checkpoints shipped with the dataset would not load under Ultralytics 8.4, so
> the pipeline auto-trained a fresh YOLO11n — that fallback is built in.)

## 2. Full pipeline on a held-out clip

Input: `82_90_120.mp4` (VISEM 30 s clip, 640×480 @ 50 fps). Pipeline =
detect → ByteTrack → CASA → WHO report. Ran in **62.6 s** for the 30 s clip.

```json
{
  "n_tracks": 219,
  "concentration_m_per_ml": 16.3,
  "total_motility_pct": 54.3,
  "progressive_motility_pct": 21.5,
  "non_progressive_pct": 32.9,
  "immotile_pct": 45.7,
  "motile_concentration_m_per_ml": 8.8,
  "progressive_concentration_m_per_ml": 3.5,
  "mean_vcl": 41.4, "mean_vap": 33.5, "mean_vsl": 25.4, "mean_lin": 57.8,
  "flags": { "concentration_below_who": false,
             "total_motility_below_who": false,
             "progressive_below_who": true }
}
```

These are biologically realistic human-sperm numbers (typical VCL 30–100 µm/s,
total motility 40–60%), and the WHO 6th-ed flags computed correctly
(progressive 21.5% < 30% → flagged). Raw output: `docs/visem-validation-report.json`.

## What this proves
The complete CV chain — detect, track, kinematics, concentration, WHO report —
runs on real microscopy video and produces sane, WHO-graded screening output.
The remaining work is calibration on actual phone optics (µm/px), a clean
train/test split, on-device export, and the hardware + regulatory tracks.
