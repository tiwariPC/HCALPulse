#!/usr/bin/env python3
# HE_SiPM: MC digi charge fractions vs Data shape 207.
# Optionally overlays two MC sources: GEN-SIM (re-digitized) and GEN-SIM-DIGI-RAW.
# Produces two plots:
#   HE_SiPM_8ts.png  — 8 TS, use8ts window, SOI at output bin 3
#   HE_SiPM_10ts.png — 10 raw TS, no window shift, SOI at hardware TS5
#
# Usage:
#   python3 plot_from_fc.py                                  # GEN-SIM-DIGI-RAW only
#   python3 plot_from_fc.py --gensim edmHcalPulseShape_gensim.root
#   python3 plot_from_fc.py --digiraw edmHcalPulseShape_digiraw.root
#   python3 plot_from_fc.py --gensim X.root --digiraw Y.root  # overlay both

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
args = parser.parse_args()

def open_root(path):
    if path is None or not os.path.exists(path):
        return None
    f = ROOT.TFile.Open(path)
    if not f or f.IsZombie():
        print(f"[WARN] cannot open {path}")
        return None
    return f


def load_profile(rfile, name):
    p = rfile.Get(f"ana/{name}") or rfile.Get(name)
    if not p or not p.InheritsFrom("TProfile"):
        rfile.ls()
        raise RuntimeError(f"{name} not found in {rfile.GetName()}")
    n  = p.GetNbinsX()
    mc = np.array([p.GetBinContent(i + 1) for i in range(n)])
    print(f"  {rfile.GetName()} / {name}: {n} bins, entries/bin[0]={p.GetBinEntries(1):.0f}")
    return mc


def load_shape_hist(rfile, name):
    """Load a shape_207/shape_208 TH1F (filled once per job by HEPulseShapeAnalyzer
    from HcalPulseShapes), unit-normalized. Returns None if not present."""
    h = rfile.Get(f"ana/{name}") or rfile.Get(name)
    if not h or not h.InheritsFrom("TH1"):
        return None
    n = h.GetNbinsX()
    s = np.array([h.GetBinContent(i + 1) for i in range(n)])
    return s / s.sum()


def _safe_ratio(num, den):
    """(num/den) - 1, with den<=0 bins set to nan instead of raising divide warnings."""
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.divide(num, den, out=np.full_like(num, np.nan, dtype=float), where=den > 0)
    return ratio - 1.0


def bin_shape_lut(s, nts, soi_ts):
    """Integrate a 1 ns/bin shape LUT into nts 25 ns slices, peak aligned to SOI bin centre."""
    s_peak_ns = int(np.argmax(s))
    offset_ns = s_peak_ns - (soi_ts * 25 + 12)
    data = np.zeros(nts)
    for ts in range(nts):
        i_lo = max(0,   ts * 25       + offset_ns)
        i_hi = min(250, (ts + 1) * 25 + offset_ns)
        if i_hi > i_lo:
            data[ts] = s[i_lo:i_hi].sum()
    if data.sum() > 0:
        data /= data.sum()
    return data


def make_plot(mc_digiraw, mc_gensim, s207, s208, nts, soi_ts, outfile):
    """Draw main + ratio panel. mc_digiraw, mc_gensim, s207, s208 may be None."""
    edges        = np.arange(nts + 1, dtype=float)
    edge_ticks   = np.arange(nts + 1, dtype=float)
    centre_ticks = np.arange(nts) + 0.5

    data       = bin_shape_lut(s207, nts, soi_ts) if s207 is not None else None
    mc_reco208 = bin_shape_lut(s208, nts, soi_ts) if s208 is not None else None

    # ratio denominator for the MC-digi-based ratio panels
    mc_ref = mc_digiraw if mc_digiraw is not None else mc_gensim

    # ratio panel 1: MC digi and shape 208 vs shape 207 (data) baseline
    have_ratio1 = data is not None and (mc_ref is not None or mc_reco208 is not None)
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
                     color="blue", linewidth=2, label=r"MC GEN-SIM-DIGI-RAW ($\Sigma Q$ > 5000 fC)")
        ymaxes.append(mc_digiraw.max())
    if mc_gensim is not None:
        hep.histplot(mc_gensim, edges, ax=ax0, histtype="step",
                     color="black", linewidth=2, linestyle="-",
                     label=r"MC GEN-SIM re-digi ($\Sigma Q$ > 5000 fC)")
        ymaxes.append(mc_gensim.max())
    if data is not None:
        hep.histplot(data, edges, ax=ax0, histtype="step",
                     color="red", linewidth=2, label="Data shape 207")
        ymaxes.append(data.max())
    if mc_reco208 is not None:
        hep.histplot(mc_reco208, edges, ax=ax0, histtype="step",
                     color="green", linewidth=2, linestyle="--", label="MC reco shape 208")
        ymaxes.append(mc_reco208.max())

    ax0.set_ylabel("Charge Fraction [A.U.]")
    ax0.set_xlim(0, nts)
    ax0.set_ylim(0, max(ymaxes) * 1.6 if ymaxes else 1)
    ax0.legend(loc="upper right", bbox_to_anchor=(0.98, 0.92), fontsize=18)
    ax0.text(0.02, 0.97, "QCD FlatPt 15-3000, Run3 2026 noPU",
             transform=ax0.transAxes, fontsize=14, verticalalignment="top",
             bbox=dict(boxstyle="square,pad=0.3", facecolor="white",
                       edgecolor="black", linewidth=1))
    hep.cms.label(llabel="Simulation", data=False, ax=ax0, loc=0, com=13.6)
    ax0.set_title("Data vs MC HE_SiPM", fontsize=14, fontweight="bold", pad=40)

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
        if mc_ref is not None:
            # match color/style to whichever MC curve mc_ref actually is (digiraw: black solid,
            # gensim fallback: blue dashed) — same convention as the main panel above
            if mc_digiraw is not None:
                mc_ref_color, mc_ref_ls, mc_ref_label = "blue", "-", "207 / MC digi (DIGI-RAW)"
            else:
                mc_ref_color, mc_ref_ls, mc_ref_label = "black", "-", "207 / MC digi (GEN-SIM)"
            ratio_mc_207 = _safe_ratio(data, mc_ref)
            hep.histplot(ratio_mc_207, edges, ax=ax1, histtype="step",
                         color=mc_ref_color, linewidth=2, linestyle=mc_ref_ls, label=mc_ref_label)
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

if f_digiraw is None and f_gensim is None:
    raise RuntimeError("No valid ROOT input files found.")

# ---- shape 207 (data) / shape 208 (MC reco) — prefer digiraw, fall back to gensim ----
shape_src = f_digiraw if f_digiraw else f_gensim
s207 = load_shape_hist(shape_src, "shape_207") if shape_src else None
s208 = load_shape_hist(shape_src, "shape_208") if shape_src else None

# ---- 8-TS plot (use8ts window, SOI at output bin 3) ----
print("8-TS profiles:")
mc8_digiraw = load_profile(f_digiraw, "frac_vs_ts") if f_digiraw else None
mc8_gensim  = load_profile(f_gensim,  "frac_vs_ts") if f_gensim  else None
make_plot(mc8_digiraw, mc8_gensim, s207, s208, nts=8, soi_ts=3, outfile="HE_SiPM_8ts.png")

# ---- 10-TS plot (raw hardware TS, no window shift, SOI at TS5) ----
print("10-TS profiles:")
mc10_digiraw = load_profile(f_digiraw, "frac_vs_ts_10") if f_digiraw else None
mc10_gensim  = load_profile(f_gensim,  "frac_vs_ts_10") if f_gensim  else None
make_plot(mc10_digiraw, mc10_gensim, s207, s208, nts=10, soi_ts=5, outfile="HE_SiPM_10ts.png")
