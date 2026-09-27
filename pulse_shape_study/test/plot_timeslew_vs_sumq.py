#!/usr/bin/env python3
# Reads the timeSlewDelay_vs_sumQ TH2F, filled by HEPulseShapeAnalyzer for
# EVERY channel with sumQ_ > 0 (not qCut-gated — filled before the qCut
# selection, see HEPulseShapeAnalyzer.cc), and plots Delta_slew =
# HcalTimeSlew::delay(sumQ_, Medium) vs sumQ_ across the full charge range.
# This shows both the sub-qCut transition region (where the M2 correction
# actually varies) and the already-saturated 0 ns plateau above qCut.
#
# Usage:
#   python3 plot_timeslew_vs_sumq.py --input edmHcalPulseShape_digiraw.root
#   python3 plot_timeslew_vs_sumq.py --input edmHcalPulseShape_data.root --qcut 5000
import argparse
import ROOT, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mplhep as hep

plt.style.use(hep.style.CMS)

parser = argparse.ArgumentParser()
parser.add_argument("--input", required=True,
                    help="ROOT file produced by HEPulseShapeAnalyzer (has ana/timeSlewDelay_vs_sumQ_<subdet>)")
parser.add_argument("--subdet", choices=["HE", "HB"], default="HE",
                    help="Which subdetector's histogram to plot (HEPulseShapeAnalyzer books both "
                         "timeSlewDelay_vs_sumQ_HE and _HB in the same job)")
parser.add_argument("--qcut", type=float, default=5000.0,
                    help="qCut value used in the cmsRun job (drawn as a reference line only — "
                         "the histogram itself is NOT qCut-gated)")
parser.add_argument("--xmax", type=float, default=10000.0,
                    help="Upper x-axis limit [fC] for the linear-scale plot. Delta_slew is already "
                         "clamped to 0 ns well below typical sumQ_ values (tens of thousands+ fC), "
                         "so the default zooms to 10000 fC to keep the transition region visible; "
                         "pass --xmax 0 to show the full range instead.")
parser.add_argument("--outfile", default=None,
                    help="Output PNG path. Defaults to timeslew_vs_sumq_<subdet>.png")
args = parser.parse_args()
if args.outfile is None:
    args.outfile = f"timeslew_vs_sumq_{args.subdet}.png"

f = ROOT.TFile.Open(args.input)
if not f or f.IsZombie():
    raise RuntimeError(f"cannot open {args.input}")

name = f"timeSlewDelay_vs_sumQ_{args.subdet}"
h = f.Get(f"ana/{name}") or f.Get(name)
if not h:
    # fall back to the old un-suffixed name (pre-HB-split ROOT files, HE-only)
    h = f.Get("ana/timeSlewDelay_vs_sumQ") or f.Get("timeSlewDelay_vs_sumQ")
    if h and args.subdet != "HE":
        raise RuntimeError(f"{name} not found and only the old un-suffixed (HE-only) histogram is "
                            f"present in {args.input} — cannot plot HB from this file "
                            "(rebuild+rerun cmsRun with the updated per-subdet HEPulseShapeAnalyzer.cc)")
if not h:
    f.ls()
    raise RuntimeError(f"{name} not found in {args.input} "
                        "(rebuild+rerun cmsRun with the updated HEPulseShapeAnalyzer.cc)")

nx, ny = h.GetNbinsX(), h.GetNbinsY()
xedges = np.array([h.GetXaxis().GetBinLowEdge(i + 1) for i in range(nx + 1)])
yedges = np.array([h.GetYaxis().GetBinLowEdge(j + 1) for j in range(ny + 1)])
counts = np.array([[h.GetBinContent(i + 1, j + 1) for i in range(nx)] for j in range(ny)])

total = counts.sum()
print(f"{args.input} [{args.subdet}]: {total:.0f} channel entries (sumQ_ > 0, unconditional — not qCut-gated)")
if total > 0:
    filled_x = np.where(counts.sum(axis=0) > 0)[0]
    filled_y = np.where(counts.sum(axis=1) > 0)[0]
    print(f"  sumQ_   range with entries: [{xedges[filled_x[0]]:.1f}, {xedges[filled_x[-1] + 1]:.1f}] fC")
    print(f"  Delta_slew range with entries: [{yedges[filled_y[0]]:.3f}, {yedges[filled_y[-1] + 1]:.3f}] ns")

fig, ax = plt.subplots(figsize=(9, 7))
masked = np.ma.masked_where(counts <= 0, counts)
mesh = ax.pcolormesh(xedges, yedges, masked, cmap="viridis")
fig.colorbar(mesh, ax=ax, label="channels / bin")
ax.axvline(args.qcut, color="red", linestyle="--", linewidth=1.5,
           label=f"qCut = {args.qcut:.0f} fC")
# Linear x-axis, capped at --xmax (default 10000 fC). Delta_slew clamps to
# 0 ns well below typical sumQ_ values, so zooming in here keeps the
# non-trivial (non-zero) region visible instead of squashing it against x=0
# over the full multi-decade range (sumQ_ extends to O(1e6) fC).
if args.xmax > 0:
    ax.set_xlim(0, args.xmax)
ax.set_xlabel("sumQ [fC] (8-TS pedestal-subtracted sum)")
ax.set_ylabel(r"$\Delta_{\rm slew}$ = HcalTimeSlew::delay(sumQ, Medium) [ns]")
ax.legend(loc="upper right", fontsize=14)
ax.text(0.02, 0.97, f"{args.subdet}, sumQ_ > 0, {total:.0f} channels (not qCut-gated)",
        transform=ax.transAxes, fontsize=13, verticalalignment="top",
        bbox=dict(boxstyle="square,pad=0.3", facecolor="white", edgecolor="black", linewidth=1))
# data=False/True and the Simulation/Preliminary label depend on whether --input
# is an MC (digiraw/gensim) or real-data (hcalpulse_data_raw_cfg.py) ROOT file —
# left generic here since this script is agnostic to which was passed in.
# NOTE: hep.cms.label() draws its own title-row text at the top of the axes —
# do not also call ax.set_title(), it will visually collide with this label.
hep.cms.label(llabel="Work in Progress", data=False, ax=ax, loc=0, com=13.6)

fig.savefig(args.outfile, dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"wrote {args.outfile}")
