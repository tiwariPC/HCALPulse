#!/usr/bin/env python3
# No-contamination check for HBHEChannelInfoPulseAnalyzer outputs (anaInfo/, anaInfoQIEPed/).
# Run from the test/ dir:  python3 check_outputs.py [file.root ...]
import sys
import numpy as np
import uproot

files = sys.argv[1:] or ["edmHcalPulseShape_digiraw.root", "edmHcalPulseShape_data.root"]
ok = True

def check(cond, msg):
    global ok
    ok &= bool(cond)
    print(f"      [{'PASS' if cond else 'FAIL'}] {msg}")

for fn in files:
    f = uproot.open(fn)
    print(f"===== {fn}")
    for d in ["anaInfo", "anaInfoQIEPed"]:
        if d not in f:
            print(f"  {d}/: MISSING (rerun cmsRun with the updated cfg)")
            continue
        print(f"  {d}/")
        for sd in ["HB", "HE"]:
            dd = f[d]
            all_, drop, passq, passq_kept = dd[f"nChan_{sd}"].values()
            n_main = dd[f"frac_vs_ts_{sd}"].member("fBinEntries")[1]
            n_drop = dd[f"frac_vs_ts_dropped_{sd}"].member("fBinEntries")[1]
            t = dd[f"pulse_{sd}"]
            a = t.arrays(["dropped", "soi"], library="np")
            print(f"    {sd}: all={all_:.0f} dropped={drop:.0f} ({drop / max(all_, 1):.1%}) "
                  f"passQ={passq:.0f} passQ&kept={passq_kept:.0f} | profile N={n_main:.0f} "
                  f"dropped-profile N={n_drop:.0f} tree N={t.num_entries}")
            check(a["dropped"].sum() == 0, "no dropped channel in pulse tree")
            check(n_main == passq_kept, "main profile entries == passQ & !dropped")
            check(t.num_entries == passq_kept, "tree entries == passQ & !dropped")
            check(passq - passq_kept == n_drop, "passQ - kept == dropped-profile entries")
            check(set(a["soi"]) <= {3}, "SOI == 3 (use8ts)")
            check(all_ < 2**53 and all_ != 2**24, "nChan not saturated (TH1D)")

print("\nALL CHECKS PASSED" if ok else "\nSOME CHECKS FAILED")
sys.exit(0 if ok else 1)
