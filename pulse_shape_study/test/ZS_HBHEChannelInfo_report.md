# HB/HE SiPM pulse shape with zero-suppression flags (HBHEChannelInfo)

*CMSSW_17_0_0_pre2 · run of 2026-09-28 · `default/` tree of the HCAL pulse-shape study*

## Summary

The MC HB charge-fraction distribution was flat, possibly because most of its
entries should be zero-suppressed. To test this, the analysis was changed to
(1) apply the `HBHEPhase1Reconstructor` drop flags
([L605](https://github.com/cms-sw/cmssw/blob/master/RecoLocalCalo/HcalRecProducers/src/HBHEPhase1Reconstructor.cc#L605))
and (2) run on `HBHEChannelInfo` instead of the digi collection
(`saveInfos = True`,
[cfi L45](https://github.com/cms-sw/cmssw/blob/master/RecoLocalCalo/HcalRecProducers/python/HBHEPhase1Reconstructor_cfi.py#L45)).

- **Both changes are in place.** The analysis now reads `HBHEChannelInfo` and keeps only
  channels with `!isDropped()`, which is exactly the set of channels reco turns into
  rechits. All 24 no-contamination checks pass.
- **The MC HB curve is no longer flat.** Its charge fraction in the sample of
  interest (SOI) rises from 0.14 to 0.57, close to MC reco shape 208 (0.59).
- **The ZS flags are applied, but the main cause of the flat shape was the pedestal.**
  - In MC, ZS flags 79 % of HB channels and removes about half of the old flat
    population above the charge cut. The remaining half still averages to a flat curve.
  - The pulse only appears once the **effective pedestal** (QIE pedestal + SiPM
    dark current) is subtracted. `HBHEChannelInfo` provides it; the old digi-based
    analysis subtracted only the QIE pedestal.
- **The earlier plots shifted shape 207 by −6 ns.**
  - They placed each LUT's peak at the centre of the SOI bin. For 207 (peak at bin
    18) that starts the array 6 ns before the SOI, instead of at the SOI start as
    stored in CMSSW. Shape 208 (peak at bin 15) was shifted by −3 ns.
  - With 207 placed as stored (section 3.4), it gives 0.51 / 0.36 in time slices
    3 / 4, against 0.66 / 0.24 in the earlier plots.
- **Data digi agrees with the unshifted shape 207.**
  - HE data matches it with no shift (rms 0.013 per time slice); HB data is within
    1 ns of it once the flat pre-SOI baseline is removed.
  - The fitted "+6 / +7 ns" (section 3.5) is mostly the plotting convention's own
    −6 ns being undone.
  - MC digi peaks about 3 ns earlier than the unshifted shape 208.
  - With only 8 integrated time slices, this shows consistency, not a unique
    shape determination (section 3.5).

## 1. Before: old digi-based analysis

The old analysis used unsuppressed MC digis (`simHcalUnsuppressedDigis`), its own
ADC→fC conversion, the QIE pedestal only, and no ZS. The selection was
ΣQ(8 TS) > 5000 fC.

<p align="center">
  <img src="HB_SiPM_8ts.png" width="45%" alt="HB, old digi-based analysis">
  <img src="HE_SiPM_8ts.png" width="45%" alt="HE, old digi-based analysis">
</p>

The MC HB curve (blue, left) is flat at about 0.12 per time slice, built from 743k
channels passing the cut. HE (right) already shows a pulse.

## 2. Implementation

### Chain

| Sample | ZS flag source | Reconstructor (`hbheInfo`, `HBHEPhase1Reconstructor` clone) | Analyzer |
|---|---|---|---|
| MC | `simHcalDigisMP`: realistic ZS (`HcalRealisticZS`, per-channel DB thresholds, Run-3 era settings) re-run on the unsuppressed digis with `markAndPass = True` | `saveInfos = True`, `dropZSmarkedPassed = True`, `saveDroppedInfos = True`, `makeRecHits = False` | `HBHEChannelInfoPulseAnalyzer` (`anaInfo`) |
| Data | hardware mark-and-pass bit in the unpacked `hcalDigis` | same | same |

The MC ZS step is needed because standard MC ZS (`simHcalDigis`, `markAndPass = False`)
*removes* suppressed channels instead of flagging them, so `zsMarkAndPass()` is never
set in MC.

The reconstructor sets, per channel
([L501–504, L605](https://github.com/cms-sw/cmssw/blob/master/RecoLocalCalo/HcalRecProducers/src/HBHEPhase1Reconstructor.cc#L605)):

```cpp
dropByZS = dropZSmarkedPassed && frame.zsMarkAndPass();
channelInfo->setChannelInfo(..., taggedBadByDb || dropByZS || badSOI);   // -> isDropped()
const bool makeThisRechit = !channelInfo->isDropped();
```

The analyzer:

- takes `tsCharge(ts) = rawCharge − pedestal` for 8 time slices, SOI at time slice 3
  (`use8ts`);
- applies ΣQ > 5000 fC;
- **skips `isDropped()` channels** in the main profile, the tree and the time-slew
  histogram;
- profiles the dropped channels separately (`frac_vs_ts_dropped_*`) as a diagnostic.

`saveDroppedInfos = True` keeps the dropped channels in the collection so they can be
counted. They never enter the result.

### Verified configuration

The values below come from the fully expanded configs (`edmConfigDump` / `runpy`, era
modifiers applied):

| Parameter | MC | Data |
|---|---|---|
| `saveInfos` | True | True |
| `dropZSmarkedPassed` | True | True |
| `saveDroppedInfos` | True | True |
| `digiLabelQIE11` | `simHcalDigisMP:HBHEQIE11DigiCollection` | `hcalDigis` |
| `saveEffectivePedestal` | True (`hbheInfo`) / False (`hbheInfoQIEPed`, cross-check) | same |
| `use8ts` / `tsFromDB` | True / False | True / False |
| `simHcalDigisMP.markAndPass` | True | n/a |
| `anaInfo.skipDropped` | True | True |

## 3. Results

### 3.1 Zero-suppression flag

| Sample | Channels read | Dropped (`isDropped`) | Dropped among channels with ΣQ > 5000 fC |
|---|---|---|---|
| MC HB | 9.07 M | **78.8 %** | 43 / 14,529 |
| MC HE | 6.77 M | **62.5 %** | 1,377 / 23,108 |
| Data HB | 11.0 M | 0.02 % | 0 |
| Data HE | 19.8 M | 0.05 % | 0 |

In data, hardware ZS already removes suppressed channels before readout, so the flag
has almost no effect. It is still applied, so data and MC are processed identically.

### 3.2 Separating the ZS effect from the pedestal effect

To separate the two effects, each job also runs a reconstructor clone with ZS applied
but the **QIE-only** pedestal (`saveEffectivePedestal = False`, directory
`anaInfoQIEPed/`). Each panel shows three curves:

- **black:** old analysis;
- **blue dashed:** ZS only;
- **red:** ZS + effective pedestal (final).

![ZS vs pedestal cross-check](zs_pedestal_check.png)

In the table, *peak* is the charge fraction in the SOI (time slice 3) and *pre-SOI* is
the summed fraction in time slices 0–2.

| | Old (no ZS, QIE ped.) | + ZS (QIE ped.) | + ZS, effective ped. (**final**) |
|---|---|---|---|
| **MC HB**: N kept / peak / pre-SOI | 743,291 / 0.138 / 0.362 | 423,321 / 0.168 / 0.346 | **14,486 / 0.566 / 0.011** |
| **MC HE** | 26,463 / 0.543 / 0.028 | 25,325 / 0.544 / 0.029 | **21,731 / 0.578 / 0.003** |
| **Data HB** | 149,671 / 0.313 / 0.155 | 150,947 / 0.312 / 0.156 | **66,322 / 0.401 / 0.073** |
| **Data HE** | 487,881 / 0.492 / 0.028 | 491,720 / 0.492 / 0.028 | **335,815 / 0.535 / −0.013** |

**MC HB, step by step:**

- **ZS** removes 396k of the 819k channels above the cut, but the kept channels are
  still flat.
- **Subtracting the dark-current pedestal** removes almost all the rest
  (423k → 14.5k) and reveals the pulse.
- **The old flat curve was a leftover pedestal.** A pedestal left in all 8 time slices
  gives a flat profile, with ΣQ sitting just above the cut (old median ≈ 5.2k fC),
  matching the old HB curve.

HE is only mildly affected: the peak goes from 0.54 to 0.58. In data, ZS changes
nothing and the effective pedestal sharpens the peak.

### 3.3 After: comparison with the target shapes, peak-centred LUTs

Here each LUT is integrated into 25 ns slices with its peak placed at the centre of the
SOI bin, the convention used by all earlier versions of these plots. This is an
implicit time shift: **−6 ns for shape 207** (peak at bin 18) and **−3 ns for shape
208** (peak at bin 15), relative to the arrays as stored in CMSSW. Section 3.4 shows
the same comparison without this shift.

<p align="center">
  <img src="HB_SiPM_8ts_chinfo.png" width="45%" alt="HB, HBHEChannelInfo with ZS flags">
  <img src="HE_SiPM_8ts_chinfo.png" width="45%" alt="HE, HBHEChannelInfo with ZS flags">
</p>

On these plots:

- **Blue:** MC digi.
- **Orange:** data digi.
- **Red:** data shape 207.
- **Green dashed:** MC reco shape 208, which is simulation-derived, not data.
- **Grey dashed:** dropped MC channels passing the charge cut, for illustration only.
  They are not part of the result.

| Charge fraction | Shape 207 (data LUT, −6 ns) | MC reco 208 (−3 ns) | MC digi | Data digi |
|---|---|---|---|---|
| HB, SOI (time slice 3) | 0.66 | 0.59 | 0.57 | 0.40 |
| HB, time slice 4 | 0.24 | 0.30 | 0.28 | 0.34 |
| HE, SOI (time slice 3) | 0.66 | 0.59 | 0.58 | 0.54 |
| HE, time slice 4 | 0.24 | 0.30 | 0.30 | 0.36 |

- **MC digi agrees with shape 208 to within a few %** in both HB and HE, but only
  because 208 is shifted −3 ns here (section 3.4).
- **Both MC and data put less charge in the SOI and more in time slice 4 than shape
  207.** Most of this is the −6 ns shift applied to 207 (section 3.4).
- **Data is noticeably later or broader than shape 207 in this placement.** Sections
  3.4 and 3.5 show this is a timing placement plus a flat baseline, not a shape
  difference.
- **The grey dropped HB curve starts at time slice 4 by construction.**
  - The Run-3 ZS keeps a channel only if the ADC count in the SOI passes the
    channel's threshold.
  - Channels that were dropped and still pass the charge cut therefore have almost
    no charge in the SOI, so their charge sits in later time slices.
  - It is 43 channels and is not part of the result.
- **The dropped HE channels above the cut (grey) have a genuine pulse shape.** They are
  probably tagged bad in the database rather than ZS noise; `isDropped()` does not
  separate the two.

### 3.4 Comparison with unshifted LUTs (array as stored)

**What changes.** Shapes 207 and 208 are lists of 250 numbers, one per nanosecond. To
compare them with the digis, each list is placed on the time axis and summed in 25 ns
time slices. Where the list starts decides how its charge splits between time slices
3 and 4:

- **Peak-centred (section 3.3):** the list is moved so that its peak sits in the middle
  of time slice 3. This moves 207 6 ns earlier and 208 3 ns earlier than stored.
- **Unshifted (this section):** the list starts at the beginning of time slice 3
  (75 ns), exactly as stored in CMSSW
  ([`HcalPulseShapes.cc`](https://github.com/cms-sw/cmssw/blob/master/CalibCalorimetry/HcalAlgos/src/HcalPulseShapes.cc#L327)).
  The 207 peak then falls at 93–94 ns.

Only the red (207) and green (208) curves move between the two placements; the
measured MC and data curves are identical.

**HB:** peak-centred (left) and unshifted (right)
<p align="center">
  <img src="HB_SiPM_8ts_chinfo.png" width="45%" alt="HB, peak-centred LUTs">
  <img src="HB_SiPM_8ts_chinfo_unshifted.png" width="45%" alt="HB, unshifted LUTs">
</p>

**HE:** peak-centred (left) and unshifted (right)
<p align="center">
  <img src="HE_SiPM_8ts_chinfo.png" width="45%" alt="HE, peak-centred LUTs">
  <img src="HE_SiPM_8ts_chinfo_unshifted.png" width="45%" alt="HE, unshifted LUTs">
</p>

**How the LUTs change** (charge fraction in time slices 3 / 4 / 5):

| | Peak-centred | Unshifted |
|---|---|---|
| Shape 207 | 0.66 / 0.24 / 0.06 | **0.51 / 0.36 / 0.08** |
| Shape 208 | 0.59 / 0.30 / 0.07 | **0.51 / 0.36 / 0.08** |

**How well each curve matches** (rms difference per time slice over time slices 3–7,
no baseline subtraction; lower is better):

| | Data vs 207 | MC vs 208 |
|---|---|---|
| HB, peak-centred | 0.127 | **0.013** |
| HB, unshifted | **0.050** | 0.040 |
| HE, peak-centred | 0.078 | **0.006** |
| HE, unshifted | **0.013** | 0.039 |

**What this shows:**

- **Data matches 207 much better when 207 is not shifted.** In HE the agreement is
  within a few % in every time slice. The disagreement in section 3.3 came from the
  placement, not from the shape.
- **HB data still has a lower SOI fraction** (0.40 against 0.51). Part of this is its
  flat +0.024 per time slice before the SOI (pileup or residual pedestal), which is not
  subtracted here. With it removed, HB data matches 207 within 1 ns of this placement
  (section 3.5).
- **MC now sits about 3 ns earlier than the stored 208.** The close MC–208 agreement in
  section 3.3 relied on the −3 ns shift of 208.
- **Unshifted, 207 and 208 are almost the same** over 8 time slices.

### 3.5 Comparison with fitted LUT phase and baseline subtraction

The placement in 3.3 is an assumption, not a measurement. If the data pulses arrive
at a different phase, charge moves between time slices 3 and 4, and the fractions
disagree even when the shape is the same. Starting from the peak-centred placement,
the plots below:

- **fit the time shift of each LUT** (1 ns steps, ±40 ns, rms over time slices ≥ SOI):
  shape 207 to data digi, shape 208 to MC digi;
- **subtract the flat pre-SOI baseline** (mean of time slices 0–2) from each digi
  curve and renormalize. This baseline comes from pileup or residual pedestal, and
  the LUTs have none.

<p align="center">
  <img src="HB_SiPM_8ts_chinfo_fit.png" width="45%" alt="HB, fitted LUT phase, baseline subtracted">
  <img src="HE_SiPM_8ts_chinfo_fit.png" width="45%" alt="HE, fitted LUT phase, baseline subtracted">
</p>

| | Fitted shift | rms per time slice | Baseline subtracted (per time slice) |
|---|---|---|---|
| HB: shape 207 vs data digi | **+7 ns** | 0.008 | data +0.024 |
| HE: shape 207 vs data digi | **+6 ns** | 0.009 | data −0.004 |
| HB: shape 208 vs MC digi | 0 ns | 0.007 | MC +0.004 |
| HE: shape 208 vs MC digi | 0 ns | 0.005 | MC +0.001 |

For comparison, the rms of data vs 207 at the peak-centred placement is 0.127 (HB) and
0.078 (HE).

The shifts are measured from the peak-centred placement. Relative to the arrays as
stored (section 3.4):

| | Shift vs peak-centred | Shift vs unshifted array |
|---|---|---|
| HB: shape 207 vs data digi | +7 ns | **+1 ns** |
| HE: shape 207 vs data digi | +6 ns | **0 ns** |
| HB / HE: shape 208 vs MC digi | 0 ns | **−3 ns** |

HB time slices 3–5 after the fit:

| | TS3 | TS4 | TS5 |
|---|---|---|---|
| Data digi | 0.468 | 0.395 | 0.098 |
| Shape 207 (+7 ns) | 0.475 | 0.389 | 0.085 |

- **Data matches shape 207 as closely as MC matches shape 208.** The data ratio in the
  first ratio panel is within about ±0.1 for both HB and HE.
- **The fitted +6 / +7 ns for 207 is not a data timing offset.** It mostly undoes the
  −6 ns implicit in the peak-centred placement: relative to the stored array, data
  sits at 0 ns (HE) and +1 ns (HB).
- **MC is about 3 ns earlier than the stored 208.** The 0 ns fit against the
  peak-centred 208 equals −3 ns against the stored array. This MC/208 offset, not a
  data offset, is the timing difference worth following up (caveat 6).
- **The phase fit and the shape are not independent.** With only 8 integrated 25 ns
  bins, a shift can absorb part of a shape difference: shape 208 also fits HE data at
  +2 ns with rms 0.010. These plots show that data is consistent with 207, not that 207
  is uniquely the right shape. Validating the shape needs the phase from an
  independent source (caveat 6).

### 3.6 No-contamination checks

`check_outputs.py` runs over MC/data × HB/HE × `anaInfo` / `anaInfoQIEPed`, which is
24 checks. **All pass.** It checks that:

- no dropped channel is in the output tree;
- profile entries = tree entries = channels passing the cut and not dropped;
- passing − kept = dropped-profile entries;
- the SOI is at time slice 3 for every channel;
- the channel counters are not saturated.

## 4. Caveats and next steps

1. **Pileup.** The MC has no pileup; the data has pileup. Pileup from earlier bunch
   crossings is expected to raise the pre-SOI and time-slice-4 fractions in data
   (e.g. HB pre-SOI 0.073 in data vs 0.011 in MC). A pileup MC sample is needed for a
   fair data/MC shape comparison.
2. **Data statistics.** Only one JetMET0 file (run 401642) was processed; more runs
   and files are needed.
3. **Data HE pre-SOI is slightly negative (−0.013).** The effective pedestal
   over-subtracts a little in data, so the dark-current values in the data conditions
   should be checked.
4. **`isDropped()` covers more than ZS.** It includes ZS, bad-in-database and bad-SOI
   channels. For the result this is the right selection, since it matches the rechit
   selection exactly, but it cannot isolate ZS alone.
5. **The charge cut now applies to dark-current-subtracted charge.** The kept channels
   have a median raw energy of ~4–7 GeV, consistent with the 4 GeV isotrack
   convention. The cut could be restated as an explicit energy cut.
6. **The LUT timing phase needs an independent reference.** Placing the LUTs as stored
   (section 3.4) removes the plotting convention's own shift, but the fitted offsets
   in section 3.5 are still partly degenerate with the shape. The remaining ~3 ns MC
   offset against the stored 208 should be checked against the phase convention reco
   uses when placing the template in time (Mahi), or against the TDC timing that
   `HBHEChannelInfo` provides in data.

## 5. Reproducing

```bash
cd /afs/cern.ch/work/p/ptiwari/public/hcal/default/CMSSW_17_0_0_pre2/src/HCALPulse/pulse_shape_study/test
./run_all.sh        # scram b -> cmsRun MC + data -> plots -> check_outputs.py
```

| File | Role |
|---|---|
| `plugins/HBHEChannelInfoPulseAnalyzer.cc` | new analyzer reading `HBHEChannelInfo` |
| `test/hcalpulse_gensimdigiraw_cfg.py`, `hcalpulse_gensim_cfg.py`, `hcalpulse_data_raw_cfg.py` | ZS flags + `saveInfos = True` reconstructor clones |
| `test/plot_from_fc.py` | peak-centred: `--dir anaInfo --tag _chinfo --show-dropped`; unshifted: `--dir anaInfo --tag _chinfo_unshifted --lut-align soi-start`; fitted: `--dir anaInfo --tag _chinfo_fit --fit-phase --subtract-baseline` |
| `test/plot_zs_pedestal_check.py` | three-step ZS vs pedestal plot |
| `test/check_outputs.py` | no-contamination checks |
| `test/run_all.sh` | full workflow; logs in `test/logs/` |

No core CMSSW file was modified. `RecoLocalCalo/HcalRecProducers` is checked out
unmodified as a reference; the reconstructor settings are overridden only through
cfg clones.
