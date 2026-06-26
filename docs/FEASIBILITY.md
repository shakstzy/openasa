# Feasibility — at-home smartphone semen analysis

**Verdict: feasible, and already a shipping product category — for concentration
and motility. Morphology, volume, and DNA fragmentation are not realistically
doable on a phone today. The hard part is not the technology, it's the FDA.**

---

## 1. Is the science real?

Yes. This is a validated, FDA-cleared product category, not a research idea.

- **YO Home Sperm Test** (Medical Electronic Systems) is a clip-on smartphone
  microscope that records a 30-second video and computes concentration + total
  + progressive motility on-device. FDA 510(k) cleared (K161493 in 2016,
  K241628 v3.0 in 2024). Peer-reviewed: **97–98% agreement** with a clinical
  lab analyzer in amateur users (n=316, *Fertility & Sterility* 2024).
- The seminal academic proof is **Kanakasabapathy et al., *Science
  Translational Medicine* 2017** (Brigham & Women's / Harvard): a <$5 phone
  attachment + microfluidic chip hit **95.8% sensitivity, 97.1% specificity**
  at clinical thresholds across 350 samples.
- **LensHooke X3 PRO SE** (FDA cleared May 2025) is the first OTC device to even
  attempt morphology — independent validation not yet public.

The honest limitation across every study: **motility correlates ~0.61–0.75 with
clinical CASA; concentration correlates >0.90.** Motility is noisier because of
phone vibration, sperm drifting out of the focal plane, and illumination
variance. A screening product should lead with concentration and treat motility
as supporting.

## 2. The optics — what it physically takes

Sperm head ≈ 5 µm, tail ≈ 50 µm. To resolve and track motile sperm you need
roughly **100–400× effective magnification, ~0.5 µm/px sample-plane scale, a
fixed 20 µm chamber depth, and 25–50 fps video.**

Three cheap optical paths, all proven:

| Approach | Mag | Parts cost | Notes |
|---|---|---|---|
| Glass ball lens (2 mm) | ~300–555× | ~$2 (AliExpress K9) / ~$20 (Edmund N-BK7) | Cheapest; tiny field, needs good centering |
| Aspheric lens clip | ~300× | ~$5–10 | Flatter field than a ball lens |
| Off-the-shelf clip scope (uHandy etc.) | ~150× | ~$70 retail | Fastest to prototype, has a wet-mount chamber |

**Illumination:** LED transillumination (a 3 mm white LED + CR2032 + diffuser,
<$1) beats the phone flash for motility video — constant, flicker-free.
**Sample holder:** a disposable 20 µm capillary-fill chamber (Leja SC20 ~$1.50–2
at volume, Cell-Vu DRM-600 ~$6 retail) gives a known volume for the
concentration math and removes the coverslip-gap error that wrecks manual
counts.

**Reference BOM (one reusable clip):** ball/aspheric lens + 3D-printed
phone-agnostic mount + LED + coin cell ≈ **$3.50–4 at scale** (sub-$20 even as a
one-off), plus the per-test disposable chamber. Injection-moldable at MOQ
500–1000 for ~$1/unit. Fork the **OpenFlexure** lens-holder geometry (CERN-OHL-S
open hardware); **do not** fork Foldscope (proprietary, not open).

## 3. The computer vision — solved, and built here

This is the part the brief asked to have "figured out and working." It is:

- **Detector:** YOLO sperm-head detection. The **VISEM-Tracking** dataset ships
  pretrained YOLOv5 weights (n/s/m/l/x) and 656k labeled bounding boxes across
  3 classes (sperm, cluster, pinhead). We validate against these on the DGX.
- **Tracker:** ByteTrack (built into Ultralytics) links detections into per-cell
  trajectories across frames.
- **Kinematics:** the OpenCASA formulas (PLOS Comput Biol 2019) turn each track
  into VCL/VAP/VSL/LIN/STR/WOB/ALH/BCF and a motility grade. **This is
  implemented and unit-tested in `openasa/casa.py` — 22 tests passing.**
- **Concentration:** cell count in the known field area × chamber depth →
  million/mL, implemented and tested in `openasa/concentration.py`.

Public training assets so nothing is rebuilt from scratch:

| Dataset | Use | Labels | License |
|---|---|---|---|
| VISEM-Tracking | detection + tracking | 656k boxes, 1.1k tracks | CC BY 4.0 |
| VISEM | motility regression | WHO % per video | research |
| HuSHeM / MHSMA / SMIDS | morphology (future) | head class / region / 3-class | CC BY / NC |
| SVIA, HSTLI (2025) | detection + segmentation | boxes + masks | mixed |

Open-source code to lean on: OpenCASA (reference math), the VISEM-Tracking
YOLOv5 baseline, EIHW/motilitAI (motility regression), SHMC-Net (morphology).

## 4. Compute

The whole CV stack runs comfortably on the **DGX Spark** (GB10, 128 GB unified).
Detector training is minutes; inference on a 30 s clip is seconds. The Spark
already hosts the voice-LLM and the homecoming frame, so openasa runs inside the
existing `comfy-venv` (torch cu130 + ultralytics + cv2) and never installs into
or competes with those — preflight confirmed GPU at 0% and 2.8 TB free before
launch.

## 5. The actual gate: regulation

This is where "ship it dirt-cheap on Amazon" collides with reality.

- A device that **analyzes a bodily specimen** is a **Class II IVD (21 CFR
  864.5220, product code POV) and requires a 510(k).** There is **no general-
  wellness exemption** for it — FDA's 2026 wellness guidance explicitly excludes
  specimen analyzers, and the WHOOP warning letter (2025) shows a "not for
  diagnosis" disclaimer does **not** save you.
- **No 510(k) = no Amazon listing.** Amazon gates Class II devices on a
  clearance letter + establishment registration. This is a hard wall.
- A 510(k) with the SQA-V / YO predicate is **clearable in ~12–18 months** —
  LensHooke and YO prove the path works for exactly this device.
- The **only** way to offer a full clinical panel (incl. morphology) without a
  510(k) is the **CLIA mail-in lab model** (Legacy, Fellow): you ship a
  collection kit, a certified lab runs the analysis. No device clearance needed,
  at the cost of overnight shipping and lab overhead.

See `docs/REGULATORY.md` for the full breakdown and the recommended sequencing.

## 6. Bottom line

| Question | Answer |
|---|---|
| Can a phone + cheap clip measure sperm concentration + motility at home? | **Yes** — validated, FDA-cleared category, ~$4 hardware. |
| Is the CV solved? | **Yes** — and built + tested in this repo. |
| Morphology / volume / DNA frag on a phone? | **No** (morphology is bleeding-edge; the rest needs the lab). |
| Can we just sell it cheap on Amazon next month? | **No** — needs a 510(k) first; that's the real timeline. |
| Is there an open-source play that ships now? | **Yes** — open hardware + CV as a research/educational tool with no diagnostic claim. |
