# cmsRun hcalpulse_data_raw_cfg.py
# Real Run-3 data counterpart to hcalpulse_gensimdigiraw_cfg.py: reads a RAW
# data file (FEDRawDataCollection only, no sim digis), runs the HCAL
# unpacker (HcalRawToDigi) to produce QIE11DataFrames, then runs the same
# HEPulseShapeAnalyzer used for MC so the "Data digi" curve is built with an
# identical ADC->fC + pedestal-subtraction + use8ts/10ts pipeline as the MC
# side (see plugins/HEPulseShapeAnalyzer.cc). shape_207 (data LUT) / shape_208
# (MC reco LUT) are also re-saved here for convenience, though plot_from_fc.py
# will normally read those from the MC digiraw file.
#
# Output: edmHcalPulseShape_data.root
#
# Input: JetMET0, run 401868 (/JetMET0/Run2026B-v1/RAW): 495 files, 14.1M events,
# ~28.8k events / ~6 GB per file.
#
# File list: jetmet0_files.txt next to this cfg (one xrootd path per line) is
# picked up automatically below; it currently holds 5 files (144k events).
# The full sorted list of the run is in jetmet0_files_run401868.full.txt; it was
# built with:
#   dasgoclient --query="file dataset=/JetMET0/Run2026B-v1/RAW run=401868" \
#     | sort | sed 's|^|root://cms-xrd-global.cern.ch/|' > jetmet0_files_run401868.full.txt
#   head -5 jetmet0_files_run401868.full.txt > jetmet0_files.txt
# (the previous run-401642 list is kept as jetmet0_files.txt.run401642.bak).
# Without jetmet0_files.txt the cfg falls back to a single file of run 401868.
import os
import FWCore.ParameterSet.Config as cms
from Configuration.Eras.Era_Run3_2026_cff import Run3_2026

process = cms.Process("S18DATA", Run3_2026)

process.load("Configuration.StandardSequences.Services_cff")
process.load("FWCore.MessageService.MessageLogger_cfi")
process.load("Configuration.StandardSequences.GeometryRecoDB_cff")
process.load("Configuration.StandardSequences.MagneticField_cff")
process.load("Configuration.StandardSequences.EndOfProcess_cff")
process.load("Configuration.StandardSequences.FrontierConditions_GlobalTag_cff")
process.load("CalibCalorimetry.HcalPlugins.Hcal_Conditions_forGlobalTag_cff")

# RAW -> HCAL digis (real data has no simHcalUnsuppressedDigis; must unpack FEDs)
process.load("EventFilter.HcalRawToDigi.HcalRawToDigi_cfi")
process.hcalDigis.InputLabel = cms.InputTag("rawDataCollector")

process.MessageLogger.cerr.threshold = cms.untracked.string("WARNING")
process.MessageLogger.cerr.FwkReport = cms.untracked.PSet(
    reportEvery = cms.untracked.int32(100),
    limit       = cms.untracked.int32(9999999),
)

from Configuration.AlCa.GlobalTag import GlobalTag
# PLACEHOLDER: pick the auto GT key matching the actual data-taking period/run
# range of the input file (e.g. via the Run Registry / conditions twiki).
# "auto:run3_data" resolves to the current prompt-reco-like GT for Run-3 data.
process.GlobalTag = GlobalTag(process.GlobalTag, "auto:run3_data", "")

process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(-1))

process.options = cms.untracked.PSet(
    numberOfThreads = cms.untracked.uint32(4),
    numberOfStreams = cms.untracked.uint32(1),
    wantSummary    = cms.untracked.bool(True),
)

# DAS dataset: /JetMET0/Run2026B-v1/RAW, run 401868 (see file-list notes at the top)
_filelist_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jetmet0_files.txt")
if os.path.exists(_filelist_path):
    with open(_filelist_path) as _f:
        _files = [line.strip() for line in _f if line.strip() and not line.strip().startswith("#")]
    print(f"[hcalpulse_data_raw_cfg] using {len(_files)} files from {_filelist_path}")
else:
    print(f"[hcalpulse_data_raw_cfg] {_filelist_path} not found, falling back to a single "
          f"run-401868 file (~29k events)")
    _files = [
        "root://cms-xrd-global.cern.ch//store/data/Run2026B/JetMET0/RAW/v1/000/401/868/00000/0015ad63-a30f-4bf3-8139-16857542c54e.root",
    ]

process.source = cms.Source("PoolSource",
    fileNames = cms.untracked.vstring(_files),
    secondaryFileNames = cms.untracked.vstring(),
)

process.TFileService = cms.Service("TFileService",
    fileName = cms.string("edmHcalPulseShape_data.root"))

process.ana = cms.EDAnalyzer("HEPulseShapeAnalyzer",
    # HcalRawToDigi ("hcalDigis") produces its main QIE11DigiCollection with NO
    # instance label (produces<QIE11DigiCollection>(); in HcalRawToDigi.cc) —
    # unlike the MC sim-digi producer, which happens to instance-label its
    # output "HBHEQIE11DigiCollection". Using that label here made the
    # consumes<QIE11DigiCollection> token resolve to nothing (isValid()=false
    # for every event, confirmed via debug logging), so frac_vs_ts stayed
    # empty regardless of statistics. Correct tag is just "hcalDigis" (empty
    # instance).
    digiTag = cms.InputTag("hcalDigis"),
    qCut    = cms.double(5000.0))

# --- HBHEChannelInfo path (ZS-aware) --------------------------------------
# Unpacked data frames already carry the hardware zsMarkAndPass bit, so no
# re-ZS is needed (unlike MC): HBHEPhase1Reconstructor with saveInfos=True and
# dropZSmarkedPassed=True sets HBHEChannelInfo::isDropped() for them directly.
process.load("RecoLocalCalo.HcalRecAlgos.hcalRecAlgoESProd_cfi")
process.load("RecoLocalCalo.HcalRecAlgos.hcalChannelPropertiesESProd_cfi")
from RecoLocalCalo.HcalRecProducers.HBHEPhase1Reconstructor_cfi import hbheprereco as _hbheprereco
process.hbheInfo = _hbheprereco.clone(
    digiLabelQIE11     = "hcalDigis",
    processQIE8        = False,
    saveInfos          = True,
    saveDroppedInfos   = True,
    dropZSmarkedPassed = True,
    makeRecHits        = False)

process.anaInfo = cms.EDAnalyzer("HBHEChannelInfoPulseAnalyzer",
    infoTag     = cms.InputTag("hbheInfo"),
    qCut        = cms.double(5000.0),
    skipDropped = cms.bool(True))

# Pedestal cross-check: same ZS flagging, QIE-only pedestal (see digiraw cfg).
process.hbheInfoQIEPed = process.hbheInfo.clone(saveEffectivePedestal = False)
process.anaInfoQIEPed = process.anaInfo.clone(infoTag = "hbheInfoQIEPed")

process.unpack_step  = cms.Path(process.hcalDigis)
process.endjob_step  = cms.EndPath(process.endOfProcess)
process.ana_step     = cms.Path(process.ana)
process.anaInfo_step = cms.Path(process.hbheInfo * process.anaInfo)
process.anaInfoQIEPed_step = cms.Path(process.hbheInfoQIEPed * process.anaInfoQIEPed)
process.schedule     = cms.Schedule(process.unpack_step, process.ana_step, process.anaInfo_step,
                                    process.anaInfoQIEPed_step, process.endjob_step)
