# HCALPulse / pulse_shape_study

Reproduce the slide-18 DPG comparison: **MC HE SiPM digi charge fractions vs data shape 207**.

## Goal

Extract per-TS pedestal-subtracted charge fractions from HE QIE11 digis (using calibrated
`HcalCoderDb`, same as HCAL reco) and compare to the hardcoded shape 207 LUT from 2017
isotrack data.  Two readout conventions are compared side by side:

| Plot | TS window | SOI position | Matches |
|---|---|---|---|
| `HE_SiPM_8ts.png` | 8 TS, `use8ts` shift applied | output bin 3 | `HBHEPhase1Reconstructor` default |
| `HE_SiPM_10ts.png` | 10 raw hardware TS, no shift | hardware TS5 | raw digi readout |

## Directory layout

```
plugins/
  HEPulseShapeAnalyzer.cc   — EDAnalyzer: ADC→fC (HcalCoderDb), pedestal subtraction,
                               fills frac_vs_ts (8 TS) and frac_vs_ts_10 (10 TS) TProfiles
  BuildFile.xml
test/
  hcalpulse_gensimdigiraw_cfg.py — reads GEN-SIM-DIGI-RAW directly, runs analyzer,
                                    writes edmHcalPulseShape_digiraw.root
  hcalpulse_gensim_cfg.py        — reads GEN-SIM, runs HCAL digitizer + analyzer,
                                    writes edmHcalPulseShape_gensim.root
  plot_from_fc.py                — reads one or both ROOT outputs, produces both PNG plots
  shape207.txt                   — shape 207 LUT (250 values @ 1 ns/bin)
  HE_SiPM_8ts.png               — output plot (8 TS, use8ts window)
  HE_SiPM_10ts.png              — output plot (10 raw TS)
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

# 4. Make plots (overlay both if both ROOT files present)
python3 plot_from_fc.py --digiraw edmHcalPulseShape_digiraw.root --gensim edmHcalPulseShape_gensim.root
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

- `HEPulseShapeAnalyzer` uses `HcalCoderDb.adc2fC()` + per-capid pedestal from
  `HcalCalibrations` — identical to `HBHEPhase1Reconstructor` L573.
- The 8-TS window shift (`tsShift = clamp(soi-3, 0, nsamp-8)`) maps raw TS5 → output bin 3,
  reproducing the reco convention.
- The 10-TS profile fills raw hardware indices directly; no shift applied, SOI stays at TS5.
- `plot_from_fc.py` aligns shape 207 to the MC SOI bin before integrating into 25 ns slices.
