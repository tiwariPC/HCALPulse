# cmsRun dump_hcal_timeslew_cfg.py
# Retrieves the HcalTimeSlew conditions payload (time-slew correction, see
# RecoLocalCalo/HcalRecAlgos/src/MahiFit.cc L29 slewFlavor_ / L274,288
# hcalTimeSlewDelay_->delay(...)) from the DB via EventSetup, using the same
# retrieval pattern as SimpleHBHEPhase1Algo (esConsumes<HcalTimeSlew,
# HcalTimeSlewRecord> with ESInputTag("", "HBHE"), read in beginRun()).
# Prints delay(fC, BiasSetting) for a few representative charges.
#
# No events are actually needed — the payload is a per-run/per-IOV EventSetup
# record, so this only requires opening one input file to get a valid Run/
# EventSetup context and processing a couple of events (set below).
#
# Output: printed to stdout via MessageLogger (HcalTimeSlewDumper category,
# LogSystem level so it always shows regardless of threshold).
import FWCore.ParameterSet.Config as cms
from Configuration.Eras.Era_Run3_2026_cff import Run3_2026

process = cms.Process("DUMPTS", Run3_2026)

process.load("Configuration.StandardSequences.Services_cff")
process.load("FWCore.MessageService.MessageLogger_cfi")
process.load("Configuration.StandardSequences.GeometryRecoDB_cff")
process.load("Configuration.StandardSequences.MagneticField_cff")
process.load("Configuration.StandardSequences.FrontierConditions_GlobalTag_cff")
process.load("CalibCalorimetry.HcalPlugins.Hcal_Conditions_forGlobalTag_cff")

process.MessageLogger.cerr.threshold = cms.untracked.string("INFO")

from Configuration.AlCa.GlobalTag import GlobalTag
# Use whichever GT matches the input sample below — MC GT shown here since
# the default input is the same MC file used elsewhere in this tree; swap to
# a data GT (see hcalpulse_data_raw_cfg.py) if pointed at a data RAW file.
process.GlobalTag = GlobalTag(process.GlobalTag, "auto:phase1_2026_realistic", "")

# Only need a run/EventSetup context, not real event content — a couple of
# events from any already-used input file is enough and avoids a new xrootd
# fetch. Reuses the same RelVal file as hcalpulse_gensimdigiraw_cfg.py.
process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(2))

process.source = cms.Source("PoolSource",
    fileNames = cms.untracked.vstring(
        "root://cms-xrd-global.cern.ch//store/relval/CMSSW_16_1_0_pre4/RelValQCD_FlatPt_15_3000HS_14/GEN-SIM-DIGI-RAW/160X_mcRun3_2026_realistic_v6_STD_RegeneratedGS_2026_noPU_20260420_140837-v3/2590000/0252edd4-ce16-48f6-9eea-3b343ed3b66e.root",
    ),
    secondaryFileNames = cms.untracked.vstring(),
)

process.dumpts = cms.EDAnalyzer("HcalTimeSlewDumper",
    # "HBHE" is the label used by SimpleHBHEPhase1Algo/MahiFit reconstruction
    # (see SimpleHBHEPhase1Algo.cc: esConsumes<...>(ESInputTag("", "HBHE"))).
    # HF has a separate "HF" payload, not used for the pulse-shape-study HE work.
    label = cms.string("HBHE"))

process.dump_step = cms.Path(process.dumpts)
process.schedule   = cms.Schedule(process.dump_step)
