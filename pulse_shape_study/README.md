# HCALPulse / pulse_shape_study

Reproduce the slide-18 DPG comparison: **MC HB/HE SiPM digi charge fractions vs data shape 207**.

## Goal

Extract per-TS pedestal-subtracted charge fractions from HB and HE QIE11 digis (using
calibrated `HcalCoderDb`, same as HCAL reco) and compare to the hardcoded shape 207 LUT
from 2017 isotrack data. HB and HE are processed separately (both are QIE11/SiPM in
Run 3) from the same digi collection in one job. Two readout conventions are compared
side by side, for each subdetector:

| Plot | Subdet | TS window | SOI position | Matches |
|---|---|---|---|---|
| `HE_SiPM_8ts.png` | HE | 8 TS, `use8ts` shift applied | output bin 3 | `HBHEPhase1Reconstructor` default |
| `HB_SiPM_8ts.png` | HB | 8 TS, `use8ts` shift applied | output bin 3 | `HBHEPhase1Reconstructor` default |

(10-TS plots were dropped — only the 8-TS `use8ts` convention is produced now.
`frac_vs_ts_10_HB`/`_HE` TProfiles are still booked/filled in the ROOT output,
just not plotted.)

## Directory layout

```
plugins/
  HEPulseShapeAnalyzer.cc   — EDAnalyzer (name kept for history; processes BOTH
                               HcalBarrel and HcalEndcap): ADC→fC (HcalCoderDb),
                               pedestal subtraction, fills frac_vs_ts_HB/_HE (8 TS)
                               and frac_vs_ts_10_HB/_HE (10 TS) TProfiles — one pair
                               per subdet from the same QIE11DigiCollection in one job;
                               also instantiates HcalPulseShapes() (no EventSetup needed)
                               once per job and fills shape_207 / shape_208 TH1F (250 bins,
                               1 ns/bin, shared target LUTs for both subdets) directly
                               from CMSSW — shape_207 = siPMShapeData2018_ (data),
                               shape_208 = siPMShapeMCRecoRun3_ (MC reco, NOT data).
                               Also fills timeSlewDelay_vs_sumQ_HB/_HE (TH2F).
  BuildFile.xml               — includes CalibCalorimetry/HcalAlgos for HcalPulseShapes
test/
  hcalpulse_gensimdigiraw_cfg.py — reads GEN-SIM-DIGI-RAW directly, runs analyzer,
                                    writes edmHcalPulseShape_digiraw.root
  hcalpulse_gensim_cfg.py        — reads GEN-SIM, runs HCAL digitizer + analyzer,
                                    writes edmHcalPulseShape_gensim.root
  hcalpulse_data_raw_cfg.py      — reads real Run-3 RAW data, runs HcalRawToDigi unpacker
                                    + analyzer, writes edmHcalPulseShape_data.root
  plot_from_fc.py                — reads ROOT output(s) (frac_vs_ts_HB/HE, shape_207,
                                    shape_208), produces HE_SiPM_8ts.png / HB_SiPM_8ts.png
                                    (10-TS plots dropped; frac_vs_ts_10_HB/_HE still
                                    booked/filled by the analyzer but not plotted)
  HE_SiPM_8ts.png                — output plot (HE, 8 TS, use8ts window)
  HB_SiPM_8ts.png                — output plot (HB, 8 TS, use8ts window)
```

## Running

All steps require a `cmsenv` shell inside `CMSSW_17_0_0_pre2`.

```bash
# 1. Build
cd /afs/cern.ch/work/p/ptiwari/public/hcal/default/CMSSW_17_0_0_pre2
cmsenv
scram b -j8

# 2. Run on GEN-SIM-DIGI-RAW — produces edmHcalPulseShape_digiraw.root
cd src/HCALPulse/pulse_shape_study/test
cmsRun hcalpulse_gensimdigiraw_cfg.py

# 3. Optionally run on GEN-SIM — produces edmHcalPulseShape_gensim.root
cmsRun hcalpulse_gensim_cfg.py

# 3b. Optionally run on real Run-3 RAW data — produces edmHcalPulseShape_data.root
#     (edit fileNames / GlobalTag in hcalpulse_data_raw_cfg.py for the run of interest)
cmsRun hcalpulse_data_raw_cfg.py

# 4. Make plots (overlay whichever ROOT files are present)
python3 plot_from_fc.py --digiraw edmHcalPulseShape_digiraw.root --gensim edmHcalPulseShape_gensim.root \
    --data edmHcalPulseShape_data.root
```

## Key parameters

| Parameter | Value | Notes |
|---|---|---|
| `qCut` | 5000 fC | Pedestal-subtracted 8-TS sum; matches isotrack slide-18 threshold |
| `digiTag` | `simHcalUnsuppressedDigis:HBHEQIE11DigiCollection` | Unsuppressed sim digis |
| Global Tag | `auto:phase1_2026_realistic` | Run-3 2026 MC conditions |
| Input sample | QCD FlatPt 15–3000, RegeneratedGS noPU | See DAS dataset in skim cfg |
| Hardware SOI | TS5 (`presamples()=5`) | HE Run-3 MC timing |

## Design notes

- `HEPulseShapeAnalyzer` processes both `HcalBarrel` and `HcalEndcap` channels from
  the single `QIE11DigiCollection` (`digiTag`) in one job, booking a separate
  TProfile/TH2F/TTree pair per subdet (`_HB`/`_HE` suffix). `plot_from_fc.py` falls
  back to the old un-suffixed names (HE-only) for ROOT files produced before this
  split, so older outputs still plot without a rerun.
- `HEPulseShapeAnalyzer` uses `HcalCoderDb.adc2fC()` + per-capid pedestal from
  `HcalCalibrations` — identical to `HBHEPhase1Reconstructor` L573.
- The 8-TS window shift (`tsShift = clamp(soi-3, 0, nsamp-8)`) maps raw TS5 → output bin 3,
  reproducing the reco convention.
- The 10-TS profile (`frac_vs_ts_10_HB`/`_HE`) fills raw hardware indices directly;
  no shift applied, SOI stays at TS5. Still booked/filled by the analyzer but no
  longer plotted by `plot_from_fc.py` (8-TS `use8ts` plots only).
- Shape 207/208 are read from the `shape_207`/`shape_208` TH1F saved in the ROOT output
  (via `load_shape_hist()`), not from a hand-maintained text file — they come straight
  from `HcalPulseShapes` at `cmsRun` time, so they automatically track whatever CMSSW
  release is in use.
- `plot_from_fc.py` aligns shape 207 to the MC SOI bin before integrating into 25 ns slices.
- Shape 208 (MC reco LUT — NOT data) is overlaid the same way, peak-aligned to the MC SOI
  bin via the same `bin_shape_lut()` helper used for shape 207.
- `hcalpulse_data_raw_cfg.py` runs on real Run-3 RAW data (e.g. JetMET0) instead of MC:
  it unpacks `FEDRawDataCollection` via `HcalRawToDigi` (`hcalDigis` module) into
  `HBHEQIE11DigiCollection`, then feeds that into the same `HEPulseShapeAnalyzer` used
  for MC (it's generic over any `QIE11DigiCollection`) with the same qCut=5000 fC. The
  resulting "Data digi" curve is a genuinely measured charge-fraction profile, distinct
  from the hardcoded "Data shape 207" LUT — do not conflate the two.
- Two ratio panels are drawn below the main panel when the inputs are available:
  1. `(207/X)-1` — shape 207 (data LUT) vs MC digi, data digi, and shape 208.
  2. `(208/MC)-1` — shape 208 (MC reco LUT) compared directly against the MC digi output.
