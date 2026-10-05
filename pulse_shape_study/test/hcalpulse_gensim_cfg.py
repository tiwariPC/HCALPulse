# cmsRun hcalpulse_gensim_cfg.py
# Reads GEN-SIM, runs digitisation_step (MixingModule noPU), then HEPulseShapeAnalyzer
# (ana/) and the ZS-aware HBHEChannelInfoPulseAnalyzer (anaInfo/).
# The digitizer uses the shape 206 compiled into the local HcalPulseShapes.cc;
# env HCAL_SHAPE206_VARIANT=y11|sipm|both selects the tuned variant (default y11).
# Output: edmHcalPulseShape_gensim.root (override with env HCALPULSE_OUT)
import os
import FWCore.ParameterSet.Config as cms
from Configuration.Eras.Era_Run3_2026_cff import Run3_2026

process = cms.Process("S18", Run3_2026)

process.load("Configuration.StandardSequences.Services_cff")
process.load("SimGeneral.HepPDTESSource.pythiapdt_cfi")
process.load("FWCore.MessageService.MessageLogger_cfi")
process.load("SimGeneral.MixingModule.mixNoPU_cfi")
process.load("Configuration.StandardSequences.GeometryRecoDB_cff")
process.load("Configuration.StandardSequences.MagneticField_cff")
process.load("Configuration.StandardSequences.Digi_cff")
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

process.mix.digitizers = cms.PSet(process.theDigitizersValid)

process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(-1))

process.options = cms.untracked.PSet(
    numberOfThreads = cms.untracked.uint32(4),
    numberOfStreams = cms.untracked.uint32(1),
    wantSummary    = cms.untracked.bool(True),
)

process.source = cms.Source("PoolSource",
    dropDescendantsOfDroppedBranches = cms.untracked.bool(False),
    fileNames = cms.untracked.vstring(
        "root://cms-xrd-global.cern.ch//store/relval/CMSSW_16_1_0_pre4/RelValQCD_FlatPt_15_3000HS_14/GEN-SIM/160X_mcRun3_2026_realistic_v6_STD_RegeneratedGS_2026_noPU_20260420_140837-v3/2590000/7608d69a-98bb-483f-b219-60caaec46ff8.root",
    ),
    inputCommands = cms.untracked.vstring(
        "keep *",
        "drop *_genParticles_*_*",
        "drop *_genParticlesForJets_*_*",
        "drop *_ak4GenJets_*_*",
        "drop *_ak8GenJets_*_*",
        "drop *_genMetTrue_*_*",
    ),
    secondaryFileNames = cms.untracked.vstring(),
)

process.TFileService = cms.Service("TFileService",
    fileName = cms.string(os.environ.get("HCALPULSE_OUT", "edmHcalPulseShape_gensim.root")))

process.ana = cms.EDAnalyzer("HEPulseShapeAnalyzer",
    digiTag = cms.InputTag("simHcalUnsuppressedDigis", "HBHEQIE11DigiCollection"),
    qCut    = cms.double(5000.0))

# --- HBHEChannelInfo path (ZS-aware) --------------------------------------
# The standard simHcalDigis from pdigi_valid uses markAndPass=False (ZS'd
# channels removed, never flagged), so re-run the same realistic ZS on
# simHcalUnsuppressedDigis with markAndPass=True, then HBHEPhase1Reconstructor
# with saveInfos=True: its dropZSmarkedPassed logic sets
# HBHEChannelInfo::isDropped() for flagged frames. saveDroppedInfos=True keeps
# them in the collection so HBHEChannelInfoPulseAnalyzer can profile them
# separately.
from SimCalorimetry.HcalZeroSuppressionProducers.hcalDigisRealistic_cfi import simHcalDigis as _simHcalDigis
process.simHcalDigisMP = _simHcalDigis.clone(markAndPass = True)

process.load("RecoLocalCalo.HcalRecAlgos.hcalRecAlgoESProd_cfi")
process.load("RecoLocalCalo.HcalRecAlgos.hcalChannelPropertiesESProd_cfi")
from RecoLocalCalo.HcalRecProducers.HBHEPhase1Reconstructor_cfi import hbheprereco as _hbheprereco
process.hbheInfo = _hbheprereco.clone(
    digiLabelQIE11     = "simHcalDigisMP:HBHEQIE11DigiCollection",
    processQIE8        = False,
    saveInfos          = True,
    saveDroppedInfos   = True,
    dropZSmarkedPassed = True,
    makeRecHits        = False)

process.anaInfo = cms.EDAnalyzer("HBHEChannelInfoPulseAnalyzer",
    infoTag     = cms.InputTag("hbheInfo"),
    qCut        = cms.double(5000.0),
    skipDropped = cms.bool(True))

# Pedestal cross-check: same ZS flagging, but QIE-only pedestal (no SiPM dark
# current) like HEPulseShapeAnalyzer — the Run-3 era default is
# saveEffectivePedestal=True.
process.hbheInfoQIEPed = process.hbheInfo.clone(saveEffectivePedestal = False)
process.anaInfoQIEPed = process.anaInfo.clone(infoTag = "hbheInfoQIEPed")

process.digitisation_step  = cms.Path(process.pdigi_valid)
process.ana_step           = cms.Path(process.ana)
process.anaInfo_step       = cms.Path(process.simHcalDigisMP * process.hbheInfo * process.anaInfo)
process.anaInfoQIEPed_step = cms.Path(process.simHcalDigisMP * process.hbheInfoQIEPed * process.anaInfoQIEPed)
process.endjob_step        = cms.EndPath(process.endOfProcess)

process.schedule = cms.Schedule(
    process.digitisation_step,
    process.ana_step,
    process.anaInfo_step,
    process.anaInfoQIEPed_step,
    process.endjob_step,
)
