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
# Example input (2026 JetMET0, Run2026A):
#   /store/data/Run2026A/JetMET0/RAW/v1/000/401/614/00000/0ab92356-5c66-483e-9ea4-7a1aeeb09ac6.root
#
# NOTE: a single RAW file can be as few as O(1-10) events (the example file
# above has only 2!) which is nowhere near enough statistics to survive the
# 5000 fC per-channel qCut. Use MANY files. Build a file list with:
#   dasgoclient --query="file dataset=/JetMET0/Run2026A-v1/RAW" \
#     | sed 's|^|root://cms-xrd-global.cern.ch/|' > jetmet0_files.txt
# and drop jetmet0_files.txt next to this cfg (one xrootd path per line) —
# it is picked up automatically below if present; otherwise falls back to
# the single hardcoded example file.
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

# DAS dataset:
#   /JetMET0/Run2026A-v1/RAW
# Get file list (see NOTE above — use many files, not one):
#   dasgoclient --query="file dataset=/JetMET0/Run2026A-v1/RAW" | sed 's|^|root://cms-xrd-global.cern.ch/|' > jetmet0_files.txt
_filelist_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jetmet0_files.txt")
if os.path.exists(_filelist_path):
    with open(_filelist_path) as _f:
        _files = [line.strip() for line in _f if line.strip() and not line.strip().startswith("#")]
    print(f"[hcalpulse_data_raw_cfg] using {len(_files)} files from {_filelist_path}")
else:
    print(f"[hcalpulse_data_raw_cfg] {_filelist_path} not found, falling back to single 2-event example file "
          f"(NOT enough statistics for qCut=5000 fC — see NOTE above)")
    _files = [
        "root://cms-xrd-global.cern.ch//store/data/Run2026A/JetMET0/RAW/v1/000/401/614/00000/0ab92356-5c66-483e-9ea4-7a1aeeb09ac6.root",
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

process.unpack_step  = cms.Path(process.hcalDigis)
process.endjob_step  = cms.EndPath(process.endOfProcess)
process.ana_step     = cms.Path(process.ana)
process.schedule     = cms.Schedule(process.unpack_step, process.ana_step, process.endjob_step)
