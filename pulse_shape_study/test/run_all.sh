#!/bin/bash
# Full pulse-shape workflow for the default/ tree:
#   build -> cmsRun (MC digiraw, data, optional gensim) -> plots -> no-contamination checks
#
# Usage (from anywhere):
#   ./run_all.sh                 # build + digiraw + data + plots + checks
#   ./run_all.sh --with-gensim   # also run hcalpulse_gensim_cfg.py (slow: re-digitizes)
#   ./run_all.sh --skip-build    # skip scram b
#   ./run_all.sh --plots-only    # no build, no cmsRun: re-plot + check existing ROOT files
#   ./run_all.sh --clean         # scram b clean before building
#
# Logs go to test/logs/<step>_<timestamp>.log. The script stops at the first failure.

set -eo pipefail

CMSSW_DIR="/afs/cern.ch/work/p/ptiwari/public/hcal/default/CMSSW_17_0_0_pre2/src"
TESTDIR="$CMSSW_DIR/HCALPulse/pulse_shape_study/test"
LOGDIR="$TESTDIR/logs"
STAMP="$(date +%Y%m%d_%H%M%S)"

DO_BUILD=1; DO_CMSRUN=1; DO_GENSIM=0; DO_CLEAN=0
for arg in "$@"; do
  case "$arg" in
    --with-gensim) DO_GENSIM=1 ;;
    --skip-build)  DO_BUILD=0 ;;
    --plots-only)  DO_BUILD=0; DO_CMSRUN=0 ;;
    --clean)       DO_CLEAN=1 ;;
    -h|--help)     sed -n 2,13p "$0"; exit 0 ;;
    *) echo "unknown option: $arg"; exit 1 ;;
  esac
done

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
  if [ "$DO_CLEAN" = 1 ]; then
    step "scram b clean"
    run_logged scram_clean scram b clean
  fi
  step "scram b -j8"
  run_logged scram_build scram b -j8
fi

cd "$TESTDIR"

# ---- cmsRun ---------------------------------------------------------------
if [ "$DO_CMSRUN" = 1 ]; then
  step "cmsRun MC GEN-SIM-DIGI-RAW -> edmHcalPulseShape_digiraw.root"
  run_logged cmsrun_digiraw cmsRun hcalpulse_gensimdigiraw_cfg.py

  step "cmsRun data RAW -> edmHcalPulseShape_data.root"
  run_logged cmsrun_data cmsRun hcalpulse_data_raw_cfg.py

  if [ "$DO_GENSIM" = 1 ]; then
    step "cmsRun MC GEN-SIM re-digi -> edmHcalPulseShape_gensim.root"
    run_logged cmsrun_gensim cmsRun hcalpulse_gensim_cfg.py
  fi
fi

# ---- plots ----------------------------------------------------------------
MC_ARGS="--digiraw edmHcalPulseShape_digiraw.root --data edmHcalPulseShape_data.root"
if [ "$DO_GENSIM" = 1 ]; then MC_ARGS="$MC_ARGS --gensim edmHcalPulseShape_gensim.root"; fi

step "plots: old digi analyzer (ana/) -> HB/HE_SiPM_8ts.png"
run_logged plot_ana python3 plot_from_fc.py $MC_ARGS

step "plots: ZS-aware HBHEChannelInfo (anaInfo/) -> HB/HE_SiPM_8ts_chinfo.png"
run_logged plot_anaInfo python3 plot_from_fc.py --dir anaInfo --tag _chinfo --show-dropped $MC_ARGS

step "plots: anaInfo/, LUT phase fitted + pre-SOI baseline subtracted -> HB/HE_SiPM_8ts_chinfo_fit.png"
run_logged plot_anaInfo_fit python3 plot_from_fc.py --dir anaInfo --tag _chinfo_fit \
  --fit-phase --subtract-baseline $MC_ARGS

step "plots: ZS vs pedestal cross-check -> zs_pedestal_check.png"
run_logged plot_zsped python3 plot_zs_pedestal_check.py \
  --digiraw edmHcalPulseShape_digiraw.root --data edmHcalPulseShape_data.root

# ---- checks ---------------------------------------------------------------
step "no-contamination checks"
CHECK_FILES="edmHcalPulseShape_digiraw.root edmHcalPulseShape_data.root"
if [ "$DO_GENSIM" = 1 ]; then CHECK_FILES="$CHECK_FILES edmHcalPulseShape_gensim.root"; fi
python3 check_outputs.py $CHECK_FILES | tee "$LOGDIR/check_${STAMP}.log"

step "done. Outputs in $TESTDIR:"
ls -1 HB_SiPM_8ts*.png HE_SiPM_8ts*.png zs_pedestal_check.png  # *_8ts, *_chinfo, *_chinfo_fit
