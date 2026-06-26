# OpenASA — Build Plan

End-to-end bill-of-materials, calibration, and deployment notes for the phone-based CASA pipeline.

## Hardware BOM

### Option A — DIY ($20-35 total)

| Part | Description | Amazon search | Est. cost |
|------|-------------|--------------|-----------|
| Clip-on microscope lens | 350x magnification, universal clip fits most phone cases | "Apexel 350x phone microscope lens" or "clip-on phone microscope 350x" | $15-25 |
| Counting chamber | Leja SC-20-01-04-04, 20 µm depth, disposable, 4-chamber | "Leja disposable counting chamber sperm" | $3-5 each |
| Sample dilution | 1x PBS or saline — standard lab supply or pharmacy saline | — | ~$2 |

**Amazon search terms:** "clip phone microscope 350x", "Apexel 350x microscope", "Leja sperm counting chamber"

### Option B — Clinical grade ($149-199)

| Part | Description |
|------|-------------|
| MiScope HS | 480x dedicated clinical clip-on scope; used in actual fertility clinics; works with iPhone + Android; validated against lab CASA |
| Leja SC-20-01-04-04 | Same counting chamber as above |

**Amazon search:** "MiScope HS phone microscope" — manufactured by Micro Science Optics.

The YOLO model was trained at 640px input. Option A yields adequate resolution; Option B gets closer to clinical-lab quality.

---

## Calibration (µm/px)

Every phone + lens combination has a different pixels-per-micron ratio. You must calibrate before results are quantitatively valid:

1. Place a **stage micrometer** (10 µm divisions) on the Leja chamber in place of a sample.
2. Record a 5-second video with the OpenASA app.
3. In the app Settings → Calibrate: count how many pixels span a known distance (e.g. 100 µm).
4. Enter the result. The app computes `um_per_px = known_um / pixel_span`.

Default `um_per_px = 0.5` in the API server is a placeholder — do NOT use for clinical estimates without calibration.

---

## WHO 6th Edition (2021) — Biomarker Coverage

| Biomarker | WHO lower reference | Phone measurable? | Status |
|-----------|--------------------|--------------------|--------|
| Concentration | ≥ 16 M/mL | Yes — cell count × chamber geometry | ✅ Built |
| Total motility | ≥ 42% | Yes — ByteTrack + VCL threshold | ✅ Built |
| Progressive motility | ≥ 30% | Yes — VAP/VSL ratio | ✅ Built |
| Volume | ≥ 1.4 mL | Hardware only — graduated collection cup | ❌ Not implemented |
| Morphology | ≥ 4% normal forms | No — requires Papanicolaou staining + 100x oil-immersion | ❌ Out of scope |
| DNA fragmentation | — | No — specialized DFI test | ❌ Out of scope |

**Phone delivers 3 of 6 parameters.** Volume is a $0.10 fix (add a marked collection cup). Morphology and DFI require a CLIA lab.

---

## System Architecture

```
iPhone (OpenASA app)
   │  video/mp4 via Tailscale
   ▼
DGX Spark (spark-2941:8420)  ←  systemd openasa-server.service
   │  FastAPI server.py
   │  comfy-venv (ultralytics + opencv)
   │  YOLO11n → ByteTrack → CASA engine → SemenReport JSON
   ▼
Supabase (vantage project / tally schema)
   │  test_results table
   ▼
Tally web app (tally.outerscope.xyz)  ←  history + trends
```

---

## Open-Source Datasets

| Dataset | Content | License | Size |
|---------|---------|---------|------|
| VISEM-Tracking (Simula, 2023) | 29 video clips, 656k bbox annotations, 3 classes, pretrained YOLO weights | CC BY 4.0 | ~8 GB |
| VISEM original (Simula, 2019) | 85 donor clips, per-clip motility labels | Research | ~18 GB |
| HuSHeM | 216 sperm head images, 4 morphology classes | CC BY 4.0 | ~10 MB |
| MHSMA | 1,457 head images, 7 morphology classes | CC BY-NC | ~50 MB |

VISEM-Tracking is the primary training + validation set. The model was validated on held-out VISEM-Tracking clips on the DGX (mAP50 = 0.987 — note: inflated due to train/val overlap on the original clips; clean split validation pending before publishing accuracy numbers publicly).

---

## iOS App (companion)

Repo: `~/Desktop/openasa-app/`
Bundle ID: `com.outerscope.openasa`
Stack: Expo SDK (bare workflow) → native iOS build via `ios-deploy ship`

**To ship to TestFlight** (one-time setup, then automated):
1. Enroll in Apple Developer Program at developer.apple.com ($99/yr)
2. In App Store Connect → Users and Access → Integrations → App Store Connect API → mint a Developer key, download the `.p8` file
3. In App Store Connect → My Apps → click `+` → New App (bundle ID: `com.outerscope.openasa`) — this is the ONLY step with no API
4. Run from the CORTANA directory:
   ```
   node .claude/skills/ios-deploy/scripts/run.mjs auth set \
     --p8 ~/Downloads/AuthKey_XXXX.p8 \
     --key-id XXXX \
     --issuer <your-issuer-uuid> \
     --team <your-team-id>
   node .claude/skills/ios-deploy/scripts/run.mjs ship ~/Desktop/openasa-app \
     --bundle-id com.outerscope.openasa
   ```
5. App appears in TestFlight ~10 minutes after upload.

After step 2-3, all future uploads are a single `ship` command — no human steps.

---

## Regulatory

Sperm analyzer = Class II IVD (21 CFR 864.5220, code POV). Requires **510(k)** for consumer sale (~12-18 months, predicate: SQA-V or YO Home Sperm Test).

**Current ship path:** Non-diagnostic open-source research tool. All output carries the disclaimer "Screening aid only. Not a diagnosis." No FDA claim = no 510(k) needed for the research version.

Commercial paths:
- **Path A** — Own-device 510(k) + CE mark (12-18 months, ~$200-500k)
- **Path B** — CLIA mail-in lab partnership (faster, adds morphology + DNA frag, Legacy/Fellow model)
