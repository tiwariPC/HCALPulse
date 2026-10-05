# HCALPulse / pulse_shape_study (shapefit/ tree)

Compares MC HB/HE SiPM digi charge fractions with the data shape 207. Here the MC is
digitized with **tuned versions of shape 206** from the `pulse_shape_fitting/` fit
loop. The MC is shown next to MC with the default shape, real Run-3 data digis, and
the MC reco shape 208.

Full write-up of the current results:
[`test/ShapeFit_HBHEChannelInfo_report.md`](test/ShapeFit_HBHEChannelInfo_report.md).

## Shape 206 variants

Shape 206 = `analyticPulseShapeSiPMHE` (SiPM kernel) ⊗ `Y11206` (scintillator + WLS
fibre kernel). Both are in `CalibCalorimetry/HcalAlgos/src/HcalPulseShapes.cc`, a
local checkout in this tree. The environment variable `HCAL_SHAPE206_VARIANT`
selects the variant at run time, so one build covers all of them:

| Variant | `Y11206()` | `analyticPulseShapeSiPMHE()` | Status |
|---|---|---|---|
| `y11` (used when the variable is unset) | iterC7 (n = 1.2, t0 = 11.2086) | 2016 original | best: digitizer-validated, closest to data |
| `sipm` | original | iterB4 (3-component) | fails at the digitizer level, pulse too fast |
| `both` | iterC7 | iterB4 | never jointly fitted; dominated by iterB4 |

- Every cmsRun log prints `[HcalPulseShapes] shape 206 variant = <v>`.
- An unknown value throws.
- Only the GEN-SIM re-digi (`hcalpulse_gensim_cfg.py`) sees the tuned shape. The
  GEN-SIM-DIGI-RAW digis come from production and always carry the default shape 206.

## Directory layout

```
plugins/
  HEPulseShapeAnalyzer.cc          — module "ana": HE QIE11 digis, ADC→fC (HcalCoderDb),
                                      QIE pedestal; frac_vs_ts (8 TS), frac_vs_ts_10 (10 TS),
                                      shape_207/208. Read by the fit loop (fit_iter.py).
  HBHEChannelInfoPulseAnalyzer.cc  — modules "anaInfo"/"anaInfoQIEPed": ZS-aware, HB+HE,
                                      reads HBHEChannelInfo (saveInfos=True reconstructor
                                      clone), skips isDropped(); frac_vs_ts_{HB,HE},
                                      frac_vs_ts_dropped_{HB,HE}, nChan_*, trees, shape_207/208
  BuildFile.xml
test/
  hcalpulse_gensim_cfg.py          — GEN-SIM → HCAL digitizer (tuned shape 206) → ana + anaInfo;
                                      output edmHcalPulseShape_gensim.root or $HCALPULSE_OUT
  hcalpulse_gensimdigiraw_cfg.py   — production GEN-SIM-DIGI-RAW (default shape) → ana + anaInfo;
                                      output edmHcalPulseShape_digiraw.root
  hcalpulse_data_raw_cfg.py        — JetMET0 RAW → HcalRawToDigi → ana + anaInfo;
                                      output edmHcalPulseShape_data.root (files: jetmet0_files.txt)
  plot_from_fc.py                  — all plots (options below)
  run_chinfo_variants.sh           — full ZS-aware workflow for the three variants
  ShapeFit_HBHEChannelInfo_report.md — results report
  edmHcalPulseShape_gensim_iter*.root, HE_SiPM_{8,10}ts_iter*.png — tagged fit-loop outputs
```

## Running

`scram b` and `cmsRun` are run manually on lxplus.

```bash
cd /afs/cern.ch/work/p/ptiwari/public/hcal/shapefit/CMSSW_17_0_0_pre2/src/HCALPulse/pulse_shape_study/test
./run_chinfo_variants.sh                    # scram b, 3x GEN-SIM re-digi, DIGI-RAW, data, plots
./run_chinfo_variants.sh --skip-build       # no scram b
./run_chinfo_variants.sh --skip-common      # reuse existing DIGI-RAW / data ROOT files
./run_chinfo_variants.sh --plots-only       # re-plot only
./run_chinfo_variants.sh --variants "y11"   # subset
```

Run a rebuild (`scram b -j8` from `src/`) after any change to `HcalPulseShapes.cc` or
`plugins/`. A single variant by hand:

```bash
HCAL_SHAPE206_VARIANT=y11 HCALPULSE_OUT=edmHcalPulseShape_gensim_chinfo_y11.root \
  cmsRun hcalpulse_gensim_cfg.py
```

Outputs (logs in `test/logs/`):

| Plot | Content |
|---|---|
| `{HB,HE}_SiPM_8ts_chinfo_{y11,sipm,both}.png` | `anaInfo`, fixed LUT phase (peak at the SOI-bin centre) |
| `{HB,HE}_SiPM_8ts_chinfo_{y11,sipm,both}_fit.png` | `anaInfo`, LUT phase fitted (207 → data digi, 208 → default MC) + pre-SOI baseline subtracted |
| `HE_SiPM_8ts.png`, `HE_SiPM_10ts.png` | `ana/` HE, fit-loop plots (`plot_from_fc.py --gensim X.root`) |

Curves on the plots:
- **Blue:** MC with the default shape (DIGI-RAW).
- **Black:** MC with the tuned shape (GEN-SIM re-digi).
- **Orange:** data digi.
- **Red:** data shape 207.
- **Green dashed:** MC reco shape 208, which is simulation-derived, not data.
- **Grey dashed:** dropped MC channels, with their count N, for illustration only.

## `plot_from_fc.py` options

| Option | Meaning |
|---|---|
| `--gensim`, `--digiraw`, `--data` | input ROOT files (any subset) |
| `--gensim-label`, `--digiraw-label` | legend labels, e.g. which tuned shape 206 |
| `--dir` | `ana` (default: HE only, 8 + 10 TS plots, fit-loop behaviour unchanged), or `anaInfo` / `anaInfoQIEPed` (HB + HE, 8 TS) |
| `--tag` | suffix of the PNG names |
| `--show-dropped` | overlay `frac_vs_ts_dropped_*` from the MC input |
| `--min-dropped-entries` | hide the dropped curve below this many channels (default 20; e.g. HB `sipm`/`both` have 1) |
| `--fit-phase` | fit the LUT time shifts (1 ns steps, ±40 ns); shifts shown in the legend |
| `--subtract-baseline` | subtract the mean pre-SOI fraction from each digi curve and renormalize |

## Key parameters

| Parameter | Value | Notes |
|---|---|---|
| `qCut` | 5000 fC | 8-TS pedestal-subtracted sum; isotrack slide-18 threshold |
| `ana.digiTag` | `simHcalUnsuppressedDigis:HBHEQIE11DigiCollection` (MC), `hcalDigis` (data) | |
| `simHcalDigisMP` | realistic ZS clone, `markAndPass = True` | MC only: flags ZS channels instead of removing them |
| `hbheInfo` | `saveInfos`, `saveDroppedInfos`, `dropZSmarkedPassed` = True, `makeRecHits` = False | `hbheInfoQIEPed`: same, `saveEffectivePedestal = False` |
| `anaInfo.skipDropped` | True | result = exactly the channels reco turns into rechits |
| Global Tag | `auto:phase1_2026_realistic` (MC), `auto:run3_data` (data, PLACEHOLDER) | |
| MC sample | QCD FlatPt 15–3000, RegeneratedGS noPU | |

## Design notes

- **The fit loop** (`pulse_shape_fitting/fit_iter.py`) reads `ana/frac_vs_ts` (HE only)
  from a tagged GEN-SIM re-digi. It runs `plot_from_fc.py --gensim <file>` with no
  other options, and that behaviour is unchanged. With `HCAL_SHAPE206_VARIANT`
  unset, the installed shape is `y11`.
- **Shape 207 phase:**
  - The fit loop aligns the 207 time origin to the SOI leading edge.
  - The fixed-phase plots put the 207 peak at the SOI-bin centre, about 6 ns earlier.
  - The data-fitted phase (+6 ns HE, +7 ns HB) agrees with the fit-loop convention.
  - Compare "vs 207" numbers only at the same phase (report, section 2.3).
- **`isDropped()`** = bad in DB ∨ ZS ∨ bad SOI. The dropped curve is a diagnostic only.
- **The `HEPulseShapeAnalyzer` 8-TS window** (`tsShift = clamp(soi-3, 0, nsamp-8)`)
  maps raw TS5 → output bin 3, the `use8ts` reco convention.
- **`HcalPulseShapes.cc` is a core CMSSW file, modified in this local checkout.** It
  holds the tuned parameters, the iteration history in comments, and the variant
  switch.
