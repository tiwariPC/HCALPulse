#!/usr/bin/env python3
# ZS vs pedestal cross-check, for both HB and HE, MC and data.
# Separates the two effects that change the charge-fraction profile when moving
# from HEPulseShapeAnalyzer (ana/) to HBHEChannelInfoPulseAnalyzer (anaInfo/):
#
#   ana/            unsuppressed digis,         QIE-only pedestal   (old pipeline)
#   anaInfoQIEPed/  ZS flag applied (isDropped), QIE-only pedestal  -> ZS effect alone
#   anaInfo/        ZS flag applied (isDropped), effective pedestal -> + dark-current pedestal
#
# (ana -> anaInfoQIEPed) is the ZS effect; (anaInfoQIEPed -> anaInfo) is the
# pedestal effect. All three are filled in one cmsRun job by the updated cfgs.
# Output: zs_pedestal_check.png (rows HB/HE, columns MC/data) + a printed
# table of qCut-passing channel counts per step.
#
# Usage:
#   python3 plot_zs_pedestal_check.py --digiraw edmHcalPulseShape_digiraw.root \
#       --data edmHcalPulseShape_data.root

import argparse, os
import numpy as np
import uproot
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mplhep as hep

plt.style.use(hep.style.CMS)

parser = argparse.ArgumentParser()
parser.add_argument("--digiraw", default=None, help="MC ROOT file (edmHcalPulseShape_digiraw.root)")
parser.add_argument("--gensim",  default=None, help="MC ROOT file (edmHcalPulseShape_gensim.root), used if no --digiraw")
parser.add_argument("--data",    default=None, help="data ROOT file (edmHcalPulseShape_data.root)")
parser.add_argument("--out",     default="zs_pedestal_check.png")
args = parser.parse_args()

STEPS = [
    ("ana",           "Unsuppressed, QIE ped. (old)", "black",   "-"),
    ("anaInfoQIEPed", "ZS applied, QIE ped.",         "tab:blue", "--"),
    ("anaInfo",       "ZS applied, effective ped.",   "tab:red",  "-"),
]


def open_root(path):
    if path is None or not os.path.exists(path):
        return None
    return uproot.open(path)


def load(rfile, d, name):
    """Return (fractions, entries) of a TProfile, or None if missing."""
    key = f"{d}/{name}"
    if rfile is None or key not in rfile:
        return None
    p = rfile[key]
    return p.values(), float(p.member("fBinEntries")[1])


mc_file = open_root(args.digiraw) or open_root(args.gensim)
data_file = open_root(args.data)
columns = [(mc_file, "MC (QCD FlatPt 15-3000, noPU)"), (data_file, "Data (JetMET0, Run3 2026)")]
columns = [c for c in columns if c[0] is not None]
if not columns:
    raise RuntimeError("No valid ROOT input files found.")

subdets = ("HB", "HE")
fig, axes = plt.subplots(len(subdets), len(columns), figsize=(10 * len(columns), 8 * len(subdets)),
                         squeeze=False)
edges = np.arange(9, dtype=float)

print(f"{'sample':<6} {'subdet':<6} {'step':<14} {'N(sumQ>qCut, kept)':>20}  frac[TS3]  sum(frac[TS0-2])")
for r, sd in enumerate(subdets):
    for c, (rf, title) in enumerate(columns):
        ax = axes[r][c]
        ymax = 0.0
        for d, label, color, ls in STEPS:
            res = load(rf, d, f"frac_vs_ts_{sd}")
            if res is None:
                print(f"{'MC' if rf is mc_file else 'data':<6} {sd:<6} {d:<14} {'(missing)':>20}")
                continue
            frac, n = res
            hep.histplot(frac, edges, ax=ax, histtype="step", color=color, linestyle=ls, linewidth=2,
                         label=f"{label} (N={n:,.0f})")
            ymax = max(ymax, frac.max())
            print(f"{'MC' if rf is mc_file else 'data':<6} {sd:<6} {d:<14} {n:>20,.0f}  {frac[3]:.4f}     {frac[:3].sum():+.4f}")
        ax.axhline(0, color="grey", linewidth=0.8)
        ax.set_xlim(0, 8)
        ax.set_ylim(min(-0.02, ax.get_ylim()[0]), max(ymax, 0.1) * 1.6)
        ax.set_xlabel("Time Slice (SOI = 3)")
        ax.set_ylabel(r"Charge fraction ($\Sigma Q$ > 5000 fC)")
        ax.set_title(f"{sd} - {title}", fontsize=18)
        ax.legend(loc="upper right", fontsize=15)

fig.tight_layout()
fig.savefig(args.out, dpi=120)
print(f"wrote {args.out}")
