#!/usr/bin/env python3
# HE_SiPM: MC digi charge fractions vs Data shape 207.
# Optionally overlays two MC sources: GEN-SIM (re-digitized with the local,
# tuned shape 206) and GEN-SIM-DIGI-RAW (production digis, default shape 206),
# plus a real Run-3 data digi source (unpacked RAW, same qCut=5000 fC, see
# hcalpulse_data_raw_cfg.py) — "Data digi", distinct from the hardcoded shape
# 207 data LUT ("Data shape 207").
#
# --dir ana (default, HEPulseShapeAnalyzer, HE only) produces:
#   HE_SiPM_8ts{tag}.png  — 8 TS, use8ts window, SOI at output bin 3
#   HE_SiPM_10ts{tag}.png — 10 raw TS, no window shift, SOI at hardware TS5
# --dir anaInfo / anaInfoQIEPed (HBHEChannelInfoPulseAnalyzer, ZS-aware, HB+HE):
#   HE_SiPM_8ts{tag}.png, HB_SiPM_8ts{tag}.png — 8 TS, SOI at output bin 3
#
# Usage:
#   python3 plot_from_fc.py --gensim edmHcalPulseShape_gensim.root          # fit loop
#   python3 plot_from_fc.py --gensim X.root --digiraw Y.root  # overlay both
#
# ZS-aware HBHEChannelInfo version for one tuned shape-206 variant (see
# run_chinfo_variants.sh):
#   python3 plot_from_fc.py --dir anaInfo --tag _chinfo_y11 --show-dropped \
#       --gensim edmHcalPulseShape_gensim_chinfo_y11.root --gensim-label "MC fitted: Y11 iterC7" \
#       --digiraw edmHcalPulseShape_digiraw.root --digiraw-label "MC default shape 206" \
#       --data edmHcalPulseShape_data.root

import argparse, os
import ROOT, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mplhep as hep

plt.style.use(hep.style.CMS)

parser = argparse.ArgumentParser()
parser.add_argument("--gensim",  default=None,
                    help="ROOT file from hcalpulse_gensim_cfg.py (GEN-SIM) named edmHcalPulseShape_gensim.root")
parser.add_argument("--digiraw", default=None,
                    help="ROOT file from run_hcalpulse.py (GEN-SIM-DIGI-RAW) named edmHcalPulseShape_digiraw.root")
parser.add_argument("--data", default=None,
                    help="ROOT file from hcalpulse_data_raw_cfg.py (real Run-3 data digis, "
                         "unpacked RAW, qCut=5000 fC) named edmHcalPulseShape_data.root")
parser.add_argument("--dir", default="ana",
                    help="TFileService directory (= analyzer module label) to read: 'ana' "
                         "(HEPulseShapeAnalyzer, unsuppressed digis, HE only) or 'anaInfo' / "
                         "'anaInfoQIEPed' (HBHEChannelInfoPulseAnalyzer, ZS-aware, HB+HE)")
parser.add_argument("--tag", default="",
                    help="suffix appended to output PNG names, e.g. _chinfo -> HB_SiPM_8ts_chinfo.png")
parser.add_argument("--show-dropped", action="store_true",
                    help="overlay MC frac_vs_ts_dropped_{HB,HE} (isDropped(), i.e. ZS-marked, "
                         "channels; anaInfo only)")
parser.add_argument("--gensim-label", default="MC GEN-SIM re-digi",
                    help="legend label for the --gensim curve, e.g. which tuned shape 206 it used")
parser.add_argument("--digiraw-label", default="MC GEN-SIM-DIGI-RAW",
                    help="legend label for the --digiraw curve")
parser.add_argument("--min-dropped-entries", type=int, default=20,
                    help="--show-dropped: skip the isDropped curve if fewer qCut-passing dropped "
                         "channels than this (a handful of channels is a single-pulse artefact)")
parser.add_argument("--fit-phase", action="store_true",
                    help="fit the time shift of each LUT instead of assuming its peak at the SOI-bin "
                         "centre: shape 207 is fitted to data digi, shape 208 to MC digi "
                         "(1 ns steps, +-40 ns, rms over TS >= SOI); fitted shifts shown in the legend")
parser.add_argument("--subtract-baseline", action="store_true",
                    help="subtract the mean pre-SOI fraction (TS0..SOI-1, pileup/residual pedestal) "
                         "from each digi curve and renormalize before comparing with the LUTs")
args = parser.parse_args()

QCUT_SUFFIX = r" ($\Sigma Q$ > 5000 fC)"


def open_root(path):
    if path is None or not os.path.exists(path):
        return None
    f = ROOT.TFile.Open(path)
    if not f or f.IsZombie():
        print(f"[WARN] cannot open {path}")
        return None
    return f


def get_obj(rfile, name):
    """Get {args.dir}/{name}. The fallback to a top-level (directory-less) object
    exists only for legacy HEPulseShapeAnalyzer files, so it is allowed only for
    --dir ana: for anaInfo/anaInfoQIEPed it would silently substitute the
    unsuppressed-digi (no ZS, no isDropped filtering) result."""
    obj = rfile.Get(f"{args.dir}/{name}")
    if obj:
        return obj
    if args.dir == "ana":
        return rfile.Get(name)
    print(f"[WARN] {args.dir}/{name} not in {rfile.GetName()} — skipped (no fallback outside --dir ana)")
    return None


def load_profile(rfile, name, required=True):
    p = get_obj(rfile, name)
    if not p or not p.InheritsFrom("TProfile"):
        if not required:
            return None
        rfile.ls()
        raise RuntimeError(f"{name} not found in {rfile.GetName()}")
    n  = p.GetNbinsX()
    mc = np.array([p.GetBinContent(i + 1) for i in range(n)])
    print(f"  {rfile.GetName()} / {name}: {n} bins, entries/bin[0]={p.GetBinEntries(1):.0f}")
    return mc


def load_shape_hist(rfile, name):
    """Load a shape_207/shape_208 TH1F (filled once per job by the analyzer
    from HcalPulseShapes), unit-normalized. Returns None if not present."""
    h = get_obj(rfile, name)
    if not h or not h.InheritsFrom("TH1"):
        return None
    n = h.GetNbinsX()
    s = np.array([h.GetBinContent(i + 1) for i in range(n)])
    return s / s.sum()


def _safe_ratio(num, den):
    """(num/den) - 1, with den<=0 bins set to nan instead of raising divide warnings.
    With --subtract-baseline the pre-SOI digi fractions scatter around 0, so bins
    where num (a LUT, exactly 0 there) is empty are masked too, instead of drawing
    spikes from (0/+-epsilon)."""
    valid = den > 0
    if args.subtract_baseline:
        valid &= num > 0
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.divide(num, den, out=np.full_like(num, np.nan, dtype=float), where=valid)
    return ratio - 1.0


def bin_shape_lut(s, nts, soi_ts, shift_ns=0):
    """Integrate a 1 ns/bin shape LUT into nts 25 ns slices, peak aligned to SOI bin centre,
    then moved by shift_ns (> 0 = later)."""
    s_peak_ns = int(np.argmax(s))
    offset_ns = s_peak_ns - (soi_ts * 25 + 12) - shift_ns
    data = np.zeros(nts)
    for ts in range(nts):
        i_lo = max(0,   ts * 25       + offset_ns)
        i_hi = min(250, (ts + 1) * 25 + offset_ns)
        if i_hi > i_lo:
            data[ts] = s[i_lo:i_hi].sum()
    if data.sum() > 0:
        data /= data.sum()
    return data


def fit_phase(s, meas, nts, soi_ts, max_shift_ns=40):
    """Shift (ns) of LUT s that best matches the measured fractions meas (rms over TS >= SOI)."""
    best_shift, best_rms = 0, np.inf
    for shift in range(-max_shift_ns, max_shift_ns + 1):
        rms = np.sqrt(np.mean((bin_shape_lut(s, nts, soi_ts, shift)[soi_ts:] - meas[soi_ts:]) ** 2))
        if rms < best_rms:
            best_shift, best_rms = shift, rms
    return best_shift, best_rms


def subtract_baseline(frac, soi_ts):
    """Remove the mean pre-SOI fraction (flat baseline) from every TS and renormalize.
    Returns (corrected fractions, baseline per TS)."""
    c = frac[:soi_ts].mean()
    out = frac - c
    return out / out.sum(), c


def make_plot(mc_digiraw, mc_gensim, data_digi, s207, s208, nts, soi_ts, outfile, subdet="HE",
              mc_dropped=None, n_dropped=0):
    """Draw main + ratio panel. mc_digiraw, mc_gensim, data_digi, s207, s208, mc_dropped may be None.
    subdet is "HE" or "HB" — used only in plot text/labels, all inputs must already
    be the matching subdet's histograms (selected by the caller). n_dropped = number of
    channels in mc_dropped (shown in its legend entry)."""
    edges        = np.arange(nts + 1, dtype=float)
    edge_ticks   = np.arange(nts + 1, dtype=float)
    centre_ticks = np.arange(nts) + 0.5

    # optional flat-baseline removal on the measured digi curves (not on the LUTs)
    baselines = {}
    if args.subtract_baseline:
        if mc_digiraw is not None: mc_digiraw, baselines["MC DIGI-RAW"] = subtract_baseline(mc_digiraw, soi_ts)
        if mc_gensim  is not None: mc_gensim,  baselines["MC GEN-SIM"]  = subtract_baseline(mc_gensim, soi_ts)
        if data_digi  is not None: data_digi,  baselines["Data"]        = subtract_baseline(data_digi, soi_ts)

    # ratio denominator for the 208-vs-MC panel. Shape 208 is derived from the
    # default shape 206, so the default-shape DIGI-RAW MC is its natural reference.
    mc_ref = mc_digiraw if mc_digiraw is not None else mc_gensim

    # LUT phase: fixed convention (peak at SOI-bin centre) or fitted to the matching digi curve
    shift207 = shift208 = 0
    if args.fit_phase:
        if s207 is not None and data_digi is not None:
            shift207, rms207 = fit_phase(s207, data_digi, nts, soi_ts)
            print(f"  [{subdet}] shape 207 fitted to data digi: shift {shift207:+d} ns, rms {rms207:.3f}")
        if s208 is not None and mc_ref is not None:
            shift208, rms208 = fit_phase(s208, mc_ref, nts, soi_ts)
            print(f"  [{subdet}] shape 208 fitted to MC digi:   shift {shift208:+d} ns, rms {rms208:.3f}")
    label207 = "Data shape 207" + (f" (shift {shift207:+d} ns, fit to data digi)"
                                   if args.fit_phase and data_digi is not None else "")
    label208 = "MC reco shape 208" + (f" (shift {shift208:+d} ns, fit to MC digi)"
                                      if args.fit_phase and mc_ref is not None else "")

    data       = bin_shape_lut(s207, nts, soi_ts, shift207) if s207 is not None else None
    mc_reco208 = bin_shape_lut(s208, nts, soi_ts, shift208) if s208 is not None else None

    # ratio panel 1: MC digi(s), data digi and shape 208 vs shape 207 (data LUT) baseline
    have_ratio1 = data is not None and (mc_ref is not None or mc_reco208 is not None or data_digi is not None)
    # ratio panel 2: shape 208 vs MC digi
    have_ratio2 = mc_reco208 is not None and mc_ref is not None

    n_ratio_rows = int(have_ratio1) + int(have_ratio2)
    ax1 = ax2 = None
    if n_ratio_rows == 2:
        fig, (ax0, ax1, ax2) = plt.subplots(
            3, 1, figsize=(10, 12),
            gridspec_kw={"height_ratios": [3, 1, 1]},
            sharex=True,
        )
        fig.subplots_adjust(hspace=0.08)
    elif n_ratio_rows == 1:
        fig, (ax0, ax_ratio) = plt.subplots(
            2, 1, figsize=(10, 8),
            gridspec_kw={"height_ratios": [3, 1]},
            sharex=True,
        )
        fig.subplots_adjust(hspace=0.05)
        if have_ratio1:
            ax1 = ax_ratio
        else:
            ax2 = ax_ratio
    else:
        fig, ax0 = plt.subplots(figsize=(10, 6))

    ymaxes = []
    if mc_digiraw is not None:
        hep.histplot(mc_digiraw, edges, ax=ax0, histtype="step",
                     color="blue", linewidth=2, label=args.digiraw_label + QCUT_SUFFIX)
        ymaxes.append(mc_digiraw.max())
    if mc_gensim is not None:
        hep.histplot(mc_gensim, edges, ax=ax0, histtype="step",
                     color="black", linewidth=2, linestyle="-",
                     label=args.gensim_label + QCUT_SUFFIX)
        ymaxes.append(mc_gensim.max())
    if data_digi is not None:
        hep.histplot(data_digi, edges, ax=ax0, histtype="step",
                     color="darkorange", linewidth=2, linestyle="-",
                     label="Data digi, Run3 2026" + QCUT_SUFFIX)
        ymaxes.append(data_digi.max())
    if data is not None:
        hep.histplot(data, edges, ax=ax0, histtype="step",
                     color="red", linewidth=2, label=label207)
        ymaxes.append(data.max())
    if mc_reco208 is not None:
        hep.histplot(mc_reco208, edges, ax=ax0, histtype="step",
                     color="green", linewidth=2, linestyle="--", label=label208)
        ymaxes.append(mc_reco208.max())
    if mc_dropped is not None:
        hep.histplot(mc_dropped, edges, ax=ax0, histtype="step",
                     color="grey", linewidth=2, linestyle="--",
                     label=f"MC digi, isDropped (ZS/bad), N={n_dropped}" + QCUT_SUFFIX)
        ymaxes.append(mc_dropped.max())

    info_text = "QCD FlatPt 15-3000, Run3 2026 noPU"
    if data_digi is not None:
        info_text += "\nData: JetMET0, Run3 2026"
    if args.dir != "ana":
        info_text += f"\nHBHEChannelInfo ({args.dir}), ZS-aware"
    n_info_lines = info_text.count("\n") + 1

    # extra legend entries / info lines need extra headroom; the legend starts
    # below the info box so the two never overlap
    n_curves = sum(x is not None for x in (mc_digiraw, mc_gensim, data_digi, data, mc_reco208, mc_dropped))
    crowded = n_curves > 4 or n_info_lines > 2
    ax0.set_ylabel("Charge Fraction [A.U.]")
    ax0.set_xlim(0, nts)
    ax0.set_ylim(0, max(ymaxes) * (2.2 if crowded else 1.6) if ymaxes else 1)
    ax0.legend(loc="upper right", bbox_to_anchor=(0.98, 0.97 - 0.055 * n_info_lines if crowded else 0.92),
               fontsize=13 if crowded else 18)
    ax0.text(0.02, 0.97, info_text,
             transform=ax0.transAxes, fontsize=14, verticalalignment="top",
             bbox=dict(boxstyle="square,pad=0.3", facecolor="white",
                       edgecolor="black", linewidth=1))
    # Comparison method, in its own box in the empty pre-SOI region (only when
    # a non-default method is used, so the fit-loop plots stay unchanged)
    if args.fit_phase or baselines:
        method_text = "LUT phase:\n" + ("  fitted" if args.fit_phase else "  peak at SOI-bin\n  centre (fixed)")
        if baselines:
            method_text += "\nPre-SOI baseline\nsubtracted (per TS):\n" + "\n".join(
                f"  {k} {v:+.3f}" for k, v in baselines.items())
        ax0.text(0.02, 0.40, method_text,
                 transform=ax0.transAxes, fontsize=12, verticalalignment="top",
                 bbox=dict(boxstyle="square,pad=0.3", facecolor="white",
                           edgecolor="grey", linewidth=1))
    # "Simulation" label only strictly true when no real data digi is overlaid
    if data_digi is not None:
        hep.cms.label(llabel="Preliminary", data=True, ax=ax0, loc=0, com=13.6)
    else:
        hep.cms.label(llabel="Simulation", data=False, ax=ax0, loc=0, com=13.6)
    ax0.set_title(f"Data vs MC {subdet}_SiPM", fontsize=14, fontweight="bold", pad=40)

    def _set_xticks(ax):
        ax.set_xticks(edge_ticks)
        ax.set_xticklabels([str(i) for i in range(nts + 1)])
        ax.set_xticks(centre_ticks, minor=True)
        ax.tick_params(axis="x", which="minor", length=4)

    def _style_ratio_ax(ax, ylabel, fontsize=20):
        ax.axhline(0, color="black", linewidth=1.0, linestyle="--")
        for y in [-0.3, -0.15, 0.15, 0.3]:
            ax.axhline(y, color="grey", linewidth=0.6, linestyle="--", alpha=0.5)
        ax.set_ylim(-0.4, 0.4)
        ax.set_yticks([-0.3, 0.0, 0.3])
        ax.set_yticklabels(["-0.3", "0.0", "0.3"])
        ax.set_ylabel(ylabel, fontsize=fontsize, loc="center")

    if ax1 is not None and have_ratio1:
        # one 207/X curve per MC source, same color/style as the main panel
        if mc_digiraw is not None:
            hep.histplot(_safe_ratio(data, mc_digiraw), edges, ax=ax1, histtype="step",
                         color="blue", linewidth=2, linestyle="-", label="207 / MC digi (DIGI-RAW)")
        if mc_gensim is not None:
            hep.histplot(_safe_ratio(data, mc_gensim), edges, ax=ax1, histtype="step",
                         color="black", linewidth=2, linestyle="-", label="207 / MC digi (GEN-SIM)")
        if data_digi is not None:
            hep.histplot(_safe_ratio(data, data_digi), edges, ax=ax1, histtype="step",
                         color="darkorange", linewidth=2, linestyle="-", label="207 / Data digi")
        if mc_reco208 is not None:
            ratio_208_207 = _safe_ratio(data, mc_reco208)
            hep.histplot(ratio_208_207, edges, ax=ax1, histtype="step",
                         color="green", linewidth=2, linestyle="--", label="207 / MC reco 208")
        _style_ratio_ax(ax1, "(207/X)$-$1")

    if ax2 is not None and have_ratio2:
        ratio_208_mc = _safe_ratio(mc_reco208, mc_ref)
        hep.histplot(ratio_208_mc, edges, ax=ax2, histtype="step",
                     color="green", linewidth=2, linestyle="--", label="MC reco 208 / MC digi")
        _style_ratio_ax(ax2, "(208/MC)$-$1")

    bottom_ax = ax2 if ax2 is not None else (ax1 if ax1 is not None else ax0)
    bottom_ax.set_xlabel("Time Slice")
    _set_xticks(bottom_ax)

    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {outfile}")


# ---- open ROOT files ----
f_digiraw = open_root(args.digiraw)
f_gensim  = open_root(args.gensim)
f_data    = open_root(args.data)

if f_digiraw is None and f_gensim is None and f_data is None:
    raise RuntimeError("No valid ROOT input files found.")

# ---- shape 207 (data) / shape 208 (MC reco) — prefer digiraw, fall back to gensim, then data ----
shape_src = f_digiraw if f_digiraw else (f_gensim if f_gensim else f_data)
s207 = load_shape_hist(shape_src, "shape_207") if shape_src else None
s208 = load_shape_hist(shape_src, "shape_208") if shape_src else None


def load_all(name, required):
    """Profile `name` from each input (None where the file/profile is absent)."""
    return tuple(load_profile(f, name, required=required) if f else None
                 for f in (f_digiraw, f_gensim, f_data))


if args.dir == "ana":
    # HEPulseShapeAnalyzer in this tree is HE-only, un-suffixed histogram names.
    # ---- 8-TS plot (use8ts window, SOI at output bin 3) ----
    print("8-TS profiles:")
    mc8_digiraw, mc8_gensim, data8_digi = load_all("frac_vs_ts", required=True)
    make_plot(mc8_digiraw, mc8_gensim, data8_digi, s207, s208, nts=8, soi_ts=3,
              outfile=f"HE_SiPM_8ts{args.tag}.png")

    # ---- 10-TS plot (raw hardware TS, no window shift, SOI at TS5) ----
    print("10-TS profiles:")
    mc10_digiraw, mc10_gensim, data10_digi = load_all("frac_vs_ts_10", required=True)
    make_plot(mc10_digiraw, mc10_gensim, data10_digi, s207, s208, nts=10, soi_ts=5,
              outfile=f"HE_SiPM_10ts{args.tag}.png")
else:
    # HBHEChannelInfoPulseAnalyzer: per-subdet names, 8 TS only (SOI at bin 3)
    for subdet in ("HE", "HB"):
        print(f"{subdet} 8-TS profiles ({args.dir}):")
        mc8_digiraw, mc8_gensim, data8_digi = load_all(f"frac_vs_ts_{subdet}", required=False)
        if mc8_digiraw is None and mc8_gensim is None and data8_digi is None:
            print(f"[WARN] no {args.dir}/frac_vs_ts_{subdet} in any input — skipping {subdet} "
                  f"(rerun cmsRun with the anaInfo path)")
            continue
        mc8_dropped, n_dropped = None, 0
        if args.show_dropped:
            mc_src = f_gensim if f_gensim else f_digiraw
            if mc_src:
                mc8_dropped = load_profile(mc_src, f"frac_vs_ts_dropped_{subdet}", required=False)
            if mc8_dropped is None:
                print(f"[WARN] --show-dropped: no frac_vs_ts_dropped_{subdet} in {args.dir}/ of the MC input")
            else:
                # every channel fills all TS bins, so bin-1 entries = channel count
                n_dropped = int(get_obj(mc_src, f"frac_vs_ts_dropped_{subdet}").GetBinEntries(1))
                if n_dropped < args.min_dropped_entries:
                    print(f"[WARN] --show-dropped: only {n_dropped} qCut-passing dropped {subdet} channel(s) "
                          f"(< --min-dropped-entries {args.min_dropped_entries}) — curve not drawn")
                    mc8_dropped = None
        make_plot(mc8_digiraw, mc8_gensim, data8_digi, s207, s208, nts=8, soi_ts=3,
                  outfile=f"{subdet}_SiPM_8ts{args.tag}.png", subdet=subdet,
                  mc_dropped=mc8_dropped, n_dropped=n_dropped)
