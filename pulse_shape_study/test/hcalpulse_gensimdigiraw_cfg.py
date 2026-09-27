# cmsRun hcalpulse_gensimdigiraw_cfg.py
# Reads GEN-SIM-DIGI-RAW directly (no intermediate skim). Drops non-HCAL collections
# at the PoolSource level to reduce memory pressure, then runs HEPulseShapeAnalyzer.
# Output: edmHcalPulseShape_digiraw.root
import FWCore.ParameterSet.Config as cms
from Configuration.Eras.Era_Run3_2026_cff import Run3_2026

process = cms.Process("S18", Run3_2026)

process.load("Configuration.StandardSequences.Services_cff")
process.load("FWCore.MessageService.MessageLogger_cfi")
process.load("Configuration.StandardSequences.GeometryRecoDB_cff")
process.load("Configuration.StandardSequences.MagneticField_cff")
process.load("Configuration.StandardSequences.EndOfProcess_cff")
process.load("Configuration.StandardSequences.FrontierConditions_GlobalTag_cff")
process.load("CalibCalorimetry.HcalPlugins.Hcal_Conditions_forGlobalTag_cff")

process.MessageLogger.cerr.threshold = cms.untracked.string("ERROR")
process.MessageLogger.cerr.FwkReport = cms.untracked.PSet(
    reportEvery = cms.untracked.int32(100),
    limit       = cms.untracked.int32(9999999),
)

from Configuration.AlCa.GlobalTag import GlobalTag
process.GlobalTag = GlobalTag(process.GlobalTag, "auto:phase1_2026_realistic", "")

process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(-1))

process.options = cms.untracked.PSet(
    numberOfThreads = cms.untracked.uint32(4),
    numberOfStreams = cms.untracked.uint32(1),
    wantSummary    = cms.untracked.bool(True),
)

# DAS dataset:
#   /RelValQCD_FlatPt_15_3000HS_14/CMSSW_16_1_0_pre4-160X_mcRun3_2026_realistic_v6_STD_RegeneratedGS_2026_noPU_20260420_140837-v3/GEN-SIM-DIGI-RAW
# Get file list:
#   dasgoclient --query="file dataset=<dataset>" | sed 's|^|root://cms-xrd-global.cern.ch/|'
process.source = cms.Source("PoolSource",
    dropDescendantsOfDroppedBranches = cms.untracked.bool(False),
    fileNames = cms.untracked.vstring(
        "root://cms-xrd-global.cern.ch//store/relval/CMSSW_16_1_0_pre4/RelValQCD_FlatPt_15_3000HS_14/GEN-SIM-DIGI-RAW/160X_mcRun3_2026_realistic_v6_STD_RegeneratedGS_2026_noPU_20260420_140837-v3/2590000/0252edd4-ce16-48f6-9eea-3b343ed3b66e.root",
    ),
    # Drop non-HCAL content to reduce memory pressure
    inputCommands = cms.untracked.vstring(
        "keep *",
        "drop FEDRawDataCollection_*_*_*",
        "drop *_hcalDigis_*_*",
        "drop *_ecalDigis_*_*",
        "drop *_ecalPreshowerDigis_*_*",
        "drop *_simEcalDigis_*_*",
        "drop *_simCastorDigis_*_*",
        "drop *_simZDCDigis_*_*",
        "drop *_simMuonCSCDigis_*_*",
        "drop *_simMuonDTDigis_*_*",
        "drop *_simMuonRPCDigis_*_*",
        "drop *_simMuonGEMDigis_*_*",
        "drop *_simMuonME0Digis_*_*",
        "drop *_simSiPixelDigis_*_*",
        "drop *_simSiStripDigis_*_*",
        "drop triggerObjectStandAlones_*_*_*",
        "drop *_TriggerResults_*_*",
        "drop *_hltTriggerSummaryAOD_*_*",
    ),
    secondaryFileNames = cms.untracked.vstring(),
)

process.TFileService = cms.Service("TFileService",
    fileName = cms.string("edmHcalPulseShape_digiraw.root"))

process.ana = cms.EDAnalyzer("HEPulseShapeAnalyzer",
    digiTag = cms.InputTag("simHcalUnsuppressedDigis", "HBHEQIE11DigiCollection"),
    qCut    = cms.double(5000.0))

process.endjob_step = cms.EndPath(process.endOfProcess)
process.ana_step    = cms.Path(process.ana)
process.schedule    = cms.Schedule(process.ana_step, process.endjob_step)
