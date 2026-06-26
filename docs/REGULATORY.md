# Regulatory reality — read this before planning go-to-market

A device that analyzes semen to report concentration or motility is a **medical
device** in the US. This is not a gray area, and disclaimers do not change it.

## The classification

| Field | Value |
|---|---|
| Class | **II** |
| Product code | **POV** (Semen Analysis Device) |
| Regulation | **21 CFR 864.5220** (Automated Differential Cell Counter) |
| Pathway | **510(k)** premarket notification — **not exempt** |
| Quality system | 21 CFR 820 (QSR) + 21 CFR 809 (IVD labeling) |

Every cleared at-home sperm test — SpermCheck (K100341), Trak (K153683), YO
(K161493 / K241628), SwimCount (K183602), LensHooke X1/X3 (K180343 / K242830) —
sits here. There is **no Class I exempt path and no Class III/PMA** device in the
category. The method (optical, smartphone, centrifuge, lateral-flow) does not
change the classification.

## Three things people wrongly think are loopholes

1. **"General wellness" exemption.** FDA's General Wellness guidance (revised
   Jan 2026) is enforcement discretion, not a legal carve-out, and it does
   **not** cover devices that analyze a bodily specimen. Fertility is not a
   listed wellness category.
2. **"Not intended to diagnose" disclaimer.** FDA decides intended use from the
   *totality* of labeling, marketing, app UI, and how customers actually use it
   (2021 Intended Use final rule). The **WHOOP warning letter (July 2025)**
   pierced exactly this disclaimer on a blood-pressure feature. The **23andMe**
   (2013) and **Agena** (2024) letters say the same: the label doesn't save you.
3. **"Sell it on Amazon cheap."** Amazon gates Class II devices on a 510(k)
   clearance letter + FDA establishment registration + manufacturer invoice.
   **No clearance = no listing.** Same for CVS/Walgreens/Target.

## The two paths that actually work

### Path A — Get the 510(k) (sell a device)
- **Predicate:** SQA-V (K021746) and/or YO (K161493). Well-trodden.
- **Work:** analytical performance study (concordance vs predicate/SQA-V), an
  OTC human-factors / lay-comprehension study, labeling review, a 21 CFR 820
  quality system.
- **Timeline:** ~12–18 months. **Cost:** typically low-to-mid six figures
  (testing + consultant + FDA fees), highly variable.
- **Labeling that clears:** categorical outputs ("Low" / "Normal"), "screening
  aid," physician-referral prompt, **no** disease names, **no** "diagnoses
  infertility," **no** "predicts pregnancy."
- **Proof it works for this exact device:** LensHooke X3 PRO SE cleared an OTC
  quantitative smartphone-class analyzer in May 2025; YO cleared a smartphone
  video CASA. The path is real.

### Path B — CLIA mail-in lab (sell a service, no 510(k))
- The Legacy / Fellow / Ro model: ship a collection kit, a **CLIA-certified
  lab** runs the analysis and returns results. A lab-developed/-performed test
  is regulated under CLIA (CMS), **not** the FDA device pathway. The 2024 FDA
  LDT rule that would have changed this was **vacated (Mar 2025) and rescinded
  (Sep 2025)** — the CLIA route is intact.
- **Lets you offer the full panel including morphology and DNA fragmentation.**
- **Cost of entry:** a CLIA lab partner + overnight cold-chain logistics, not a
  510(k). Friction is shipping + 48 h turnaround, not regulatory.

## Recommended sequencing (de-risks the build)

1. **Now — open-source research/education track.** Publish the hardware + CV as
   a non-diagnostic, research/educational tool ("for educational use; not a
   medical device; not for diagnosis"). This ships immediately, builds a
   community, and — critically — **harvests real-world paired video + lab data**
   that becomes the analytical-validation dataset for a future 510(k). Keep it
   genuinely non-diagnostic: no "Low/Normal fertility" verdicts in that build.
2. **In parallel — decide the commercial wrapper:** Path A (own device, ~12–18
   mo) vs Path B (CLIA partner, faster to revenue, fuller panel). Path B can
   fund Path A.
3. **Build to the 510(k) from day one** even on the open track: 21 CFR 820
   design controls, traceable calibration, and a frozen algorithm version cost
   almost nothing to maintain early and are expensive to retrofit.

The engineering is the easy 20%. The clearance + clinical validation is the 80%
that determines whether this is a product or a GitHub repo.
