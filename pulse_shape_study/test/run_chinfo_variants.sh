#!/bin/bash
# ZS-aware (HBHEChannelInfo, anaInfo/) HB/HE 8-TS plots for the three tuned
# shape-206 variants of this shapefit/ tree. One build serves all three: the
# variant is picked at runtime by HCAL_SHAPE206_VARIANT in
# CalibCalorimetry/HcalAlgos/src/HcalPulseShapes.cc:
#   y11  — Y11206 iterC7 + SiPM (analyticPulseShapeSiPMHE) 2016 original
#   sipm — Y11206 original + SiPM iterB4 (3-component)
#   both — Y11206 iterC7 + SiPM iterB4 (never fitted jointly)
# Each plot overlays: fitted MC (GEN-SIM re-digi), default-shape MC
# (GEN-SIM-DIGI-RAW), data digi (JetMET0 RAW), MC isDropped, shapes 207/208.
#
# Usage (from anywhere; run MANUALLY on lxplus):
#   ./run_chinfo_variants.sh                  # build + 3x gensim + digiraw + data + plots
#   ./run_chinfo_variants.sh --skip-build     # skip scram b
#   ./run_chinfo_variants.sh --skip-common    # reuse existing digiraw/data ROOT files
#   ./run_chinfo_variants.sh --plots-only     # no build, no cmsRun: re-plot existing ROOT files
#   ./run_chinfo_variants.sh --variants "y11 both"   # subset of variants
#
# Outputs: {HB,HE}_SiPM_8ts_chinfo_{y11,sipm,both}{,_unshifted,_fit}.png
#   (no suffix: LUT peak at SOI-bin centre; _unshifted: --lut-align soi-start, LUT as stored;
#    _fit: --fit-phase --subtract-baseline)
# Data: JetMET0 run 401868 (/JetMET0/Run2026B-v1/RAW), file list in jetmet0_files.txt.
# Logs go to test/logs/<step>_<timestamp>.log. The script stops at the first failure.

set -eo pipefail

CMSSW_DIR="/afs/cern.ch/work/p/ptiwari/public/hcal/shapefit/CMSSW_17_0_0_pre2/src"
TESTDIR="$CMSSW_DIR/HCALPulse/pulse_shape_study/test"
LOGDIR="$TESTDIR/logs"
STAMP="$(date +%Y%m%d_%H%M%S)"

DO_BUILD=1; DO_CMSRUN=1; DO_COMMON=1; VARIANTS="y11 sipm both"
while [ $# -gt 0 ]; do
  case "$1" in
    --skip-build)  DO_BUILD=0 ;;
    --skip-common) DO_COMMON=0 ;;
    --plots-only)  DO_BUILD=0; DO_CMSRUN=0 ;;
    --variants)    shift; VARIANTS="$1" ;;
    -h|--help)     sed -n 2,23p "$0"; exit 0 ;;
    *) echo "unknown option: $1"; exit 1 ;;
  esac
  shift
done

variant_label() {
  case "$1" in
    y11)  echo "MC fitted: Y11 iterC7 + SiPM 2016 (GEN-SIM re-digi)" ;;
    sipm) echo "MC fitted: Y11 orig. + SiPM iterB4 (GEN-SIM re-digi)" ;;
    both) echo "MC fitted: Y11 iterC7 + SiPM iterB4 (GEN-SIM re-digi)" ;;
    *) echo "unknown variant: $1" >&2; exit 1 ;;
  esac
}
for v in $VARIANTS; do variant_label "$v" > /dev/null; done

mkdir -p "$LOGDIR"
step() { echo; echo "=== [$(date +%H:%M:%S)] $*"; }
run_logged() {   # run_logged <name> <cmd...>
  local name="$1"; shift
  local log="$LOGDIR/${name}_${STAMP}.log"
  echo "    -> $log"
  "$@" > "$log" 2>&1 || { echo "!!! $name FAILED — last lines of $log:"; tail -20 "$log"; exit 1; }
}

# ---- environment (cmsenv) -------------------------------------------------
step "cmsenv in $CMSSW_DIR"
source /cvmfs/cms.cern.ch/cmsset_default.sh
cd "$CMSSW_DIR"
eval "$(scram runtime -sh)"
echo "    CMSSW_BASE=$CMSSW_BASE"

# ---- build ----------------------------------------------------------------
if [ "$DO_BUILD" = 1 ]; then
  step "scram b -j8"
  run_logged scram_build scram b -j8
fi

cd "$TESTDIR"

# ---- cmsRun ---------------------------------------------------------------
if [ "$DO_CMSRUN" = 1 ]; then
  for v in $VARIANTS; do
    out="edmHcalPulseShape_gensim_chinfo_${v}.root"
    step "cmsRun GEN-SIM re-digi, HCAL_SHAPE206_VARIANT=$v -> $out"
    HCAL_SHAPE206_VARIANT="$v" HCALPULSE_OUT="$out" run_logged "cmsrun_gensim_chinfo_${v}" \
      cmsRun hcalpulse_gensim_cfg.py
    # the library prints the active variant once; make sure it is the requested one
    grep -q "shape 206 variant = $v" "$LOGDIR/cmsrun_gensim_chinfo_${v}_${STAMP}.log" \
      || { echo "!!! variant line '$v' not found in cmsRun log"; exit 1; }
  done

  if [ "$DO_COMMON" = 1 ]; then
    step "cmsRun MC GEN-SIM-DIGI-RAW (default shape 206) -> edmHcalPulseShape_digiraw.root"
    run_logged cmsrun_digiraw cmsRun hcalpulse_gensimdigiraw_cfg.py

    step "cmsRun data RAW -> edmHcalPulseShape_data.root"
    run_logged cmsrun_data cmsRun hcalpulse_data_raw_cfg.py
  fi
fi

# ---- plots ----------------------------------------------------------------
COMMON_ARGS="--dir anaInfo --show-dropped --digiraw edmHcalPulseShape_digiraw.root"
COMMON_ARGS="$COMMON_ARGS --data edmHcalPulseShape_data.root"
for v in $VARIANTS; do
  VARIANT_ARGS=(--gensim "edmHcalPulseShape_gensim_chinfo_${v}.root"
                --gensim-label "$(variant_label "$v")"
                --digiraw-label "MC default shape 206 (GEN-SIM-DIGI-RAW)")
  step "plots: variant $v -> HB/HE_SiPM_8ts_chinfo_${v}.png"
  run_logged "plot_chinfo_${v}" python3 plot_from_fc.py $COMMON_ARGS --tag "_chinfo_${v}" "${VARIANT_ARGS[@]}"

  step "plots: variant $v, LUTs unshifted (bin 0 at SOI start) -> HB/HE_SiPM_8ts_chinfo_${v}_unshifted.png"
  run_logged "plot_chinfo_${v}_unshifted" python3 plot_from_fc.py $COMMON_ARGS --tag "_chinfo_${v}_unshifted" \
    --lut-align soi-start "${VARIANT_ARGS[@]}"

  step "plots: variant $v, LUT phase fitted + pre-SOI baseline subtracted -> HB/HE_SiPM_8ts_chinfo_${v}_fit.png"
  run_logged "plot_chinfo_${v}_fit" python3 plot_from_fc.py $COMMON_ARGS --tag "_chinfo_${v}_fit" \
    --fit-phase --subtract-baseline "${VARIANT_ARGS[@]}"
done

step "done. Outputs in $TESTDIR:"
for v in $VARIANTS; do
  ls -1 {HB,HE}_SiPM_8ts_chinfo_${v}.png {HB,HE}_SiPM_8ts_chinfo_${v}_unshifted.png \
        {HB,HE}_SiPM_8ts_chinfo_${v}_fit.png
done
