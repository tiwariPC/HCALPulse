// HEPulseShapeAnalyzer.cc
// Slide-18-style MC comparison: HB and HE QIE11, per-TS pedestal-subtracted
// charge fractions, computed separately for each subdetector.
// Uses HcalCoderDb (same as reco) for ADC->fC, then subtracts per-capid pedestal.
// Applies the same use8ts logic as HBHEPhase1Reconstructor (use8ts=True default):
//   tsShift = clamp(soi - soiWanted, 0, nRead - 8),  soiWanted = 3
//   copies 8 TS starting at tsShift, so SOI always falls at output bin 3.
// TProfile output = mean charge fraction vs output TS (0-7, SOI at 3).
// Despite the class name (kept for history/back-compat with existing cfgs),
// this analyzer processes BOTH HcalBarrel and HcalEndcap channels from the
// same QIE11DigiCollection and books separate HB/HE histograms/trees for each
// — nothing here is HE-specific anymore.
//
// Also retrieves the HcalTimeSlew ("HBHE" label) conditions payload and, for
// every channel with sumQ_ > 0 (BEFORE the qCut selection, so the transition
// region is visible, not just the already-saturated plateau above qCut),
// computes Delta_slew = HcalTimeSlew::delay(sumQ_, Medium) — the M2 time-slew
// correction (see CalibCalorimetry/HcalAlgos/src/HcalTimeSlew.cc) — and fills
// a per-subdet timeSlewDelay_vs_sumQ (TH2F, log-x). The "timeSlewDelay" tree
// branch is still only filled for qCut-passing channels, alongside the other
// per-channel branches used by the main SiPM shape comparison.

#include "FWCore/Framework/interface/one/EDAnalyzer.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/EventSetup.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/ServiceRegistry/interface/Service.h"
#include "CommonTools/UtilAlgos/interface/TFileService.h"

#include "DataFormats/HcalDigi/interface/HcalDigiCollections.h"
#include "DataFormats/HcalDigi/interface/QIE11DataFrame.h"
#include "DataFormats/HcalDetId/interface/HcalDetId.h"

#include "CalibFormats/HcalObjects/interface/HcalDbService.h"
#include "CalibFormats/HcalObjects/interface/HcalDbRecord.h"
#include "CalibFormats/HcalObjects/interface/HcalCoderDb.h"
#include "CalibFormats/HcalObjects/interface/HcalCalibrations.h"
#include "CondFormats/HcalObjects/interface/HcalQIECoder.h"
#include "CondFormats/HcalObjects/interface/HcalQIEShape.h"
#include "CalibCalorimetry/HcalAlgos/interface/HcalPulseShapes.h"
#include "CalibCalorimetry/HcalAlgos/interface/HcalTimeSlew.h"
#include "CondFormats/DataRecord/interface/HcalTimeSlewRecord.h"

#include "TProfile.h"
#include "TH1F.h"
#include "TH2F.h"
#include "TTree.h"
#include "TString.h"
#include <algorithm>
#include <cmath>
#include <vector>

namespace {
  // HcalBarrel=1, HcalEndcap=2 (DataFormats/HcalDetId/interface/HcalSubdetector.h)
  enum SubdetIdx { kHB = 0, kHE = 1, kNSubdet = 2 };
  const char* subdetName[kNSubdet] = {"HB", "HE"};
}

class HEPulseShapeAnalyzer : public edm::one::EDAnalyzer<edm::one::SharedResources> {
public:
  explicit HEPulseShapeAnalyzer(const edm::ParameterSet&);
  void analyze(const edm::Event&, const edm::EventSetup&) override;
private:
  edm::EDGetTokenT<QIE11DigiCollection> tok_;
  edm::ESGetToken<HcalDbService, HcalDbRecord> db_;
  edm::ESGetToken<HcalTimeSlew, HcalTimeSlewRecord> timeSlewTok_;
  double qcut_;
  TProfile* prof_[kNSubdet];
  TProfile* prof10_[kNSubdet];
  TH2F* timeSlewVsSumQ_[kNSubdet];
  TTree* tree_[kNSubdet];
  int ieta_, iphi_, depth_, soi_, nsamp_;
  float sumQ_;
  float timeSlewDelay_;
  std::vector<float> q_;
};

HEPulseShapeAnalyzer::HEPulseShapeAnalyzer(const edm::ParameterSet& ps)
  : tok_(consumes<QIE11DigiCollection>(ps.getParameter<edm::InputTag>("digiTag"))),
    db_(esConsumes<HcalDbService, HcalDbRecord>()),
    // "HBHE" label — same retrieval pattern as SimpleHBHEPhase1Algo/MahiFit
    // and plugins/HcalTimeSlewDumper.cc. One payload covers both HB and HE.
    timeSlewTok_(esConsumes<HcalTimeSlew, HcalTimeSlewRecord>(edm::ESInputTag("", "HBHE"))),
    qcut_(ps.getParameter<double>("qCut")) {
  usesResource("TFileService");
  edm::Service<TFileService> fs;

  for (int s = 0; s < kNSubdet; ++s) {
    const char* sd = subdetName[s];
    // 8 output TS (0-7), SOI at bin 3 — matches HBHEPhase1Reconstructor use8ts=True convention
    prof_[s] = fs->make<TProfile>(Form("frac_vs_ts_%s", sd),
        Form("%s_SiPM mean charge fraction;Time Slice;A.U.", sd), 8, -0.5, 7.5);
    // 10 raw TS (0-9), no window shift — SOI stays at hardware presamples position
    prof10_[s] = fs->make<TProfile>(Form("frac_vs_ts_10_%s", sd),
        Form("%s_SiPM mean charge fraction (10 TS raw);Time Slice;A.U.", sd), 10, -0.5, 9.5);
    // Time-slew delay (M2, BiasSetting::Medium) vs sumQ_, filled for ALL channels
    // with sumQ_ > 0 (not just qCut-passing ones) so the transition from non-zero
    // Delta_slew down to the clamped 0 ns floor is visible, not just the
    // already-saturated plateau above qCut. Log-spaced x bins from 1 fC to 2e6
    // fC since sumQ_ spans several decades; linear bins would squash the
    // interesting low-charge region into a sliver near x=0.
    const int nxbins = 100;
    std::vector<double> xedges(nxbins + 1);
    const double xlo = 1.0, xhi = 2.0e6;
    for (int i = 0; i <= nxbins; ++i)
      xedges[i] = xlo * std::pow(xhi / xlo, double(i) / nxbins);
    timeSlewVsSumQ_[s] = fs->make<TH2F>(Form("timeSlewDelay_vs_sumQ_%s", sd),
        Form("HcalTimeSlew M2 delay (Medium) vs sumQ_, %s, sumQ_ > 0;sumQ_ [fC];Delta_slew [ns]", sd),
        nxbins, xedges.data(), 100, 0.0, 12.0);

    tree_[s] = fs->make<TTree>(Form("pulse_%s", sd), "");
    tree_[s]->Branch("ieta",&ieta_); tree_[s]->Branch("iphi",&iphi_); tree_[s]->Branch("depth",&depth_);
    tree_[s]->Branch("soi",&soi_);  tree_[s]->Branch("nsamp",&nsamp_); tree_[s]->Branch("sumQ",&sumQ_);
    tree_[s]->Branch("timeSlewDelay",&timeSlewDelay_);
    tree_[s]->Branch("q",&q_);
  }

  // Save shape 207 (siPMShapeData2018_, 2017 isotrack DATA LUT) and shape 208
  // (siPMShapeMCRecoRun3_, shape 206 + 7.2 ns shift, MC RECO LUT — not data)
  // directly from CMSSW, so plot_from_fc.py can read them from this ROOT
  // file instead of a hand-maintained text dump. HcalPulseShapes' no-arg
  // constructor needs no EventSetup/conditions — it precomputes all
  // hardcoded shapes (206/207/208/...) in its constructor body. These are
  // subdetector-agnostic (same LUT used as the target shape for both HB/HE
  // in this study), so only saved once, not per-subdet.
  HcalPulseShapes shapes;
  for (int shapeId : {207, 208}) {
    const HcalPulseShapes::Shape& sh = shapes.getShape(shapeId);
    auto h = fs->make<TH1F>(Form("shape_%d", shapeId),
                             Form("HcalPulseShapes shape %d;Time [ns];Value", shapeId),
                             sh.nbins(), 0.0, double(sh.nbins()));
    for (int i = 0; i < sh.nbins(); ++i)
      h->SetBinContent(i + 1, sh.data()[i]);
  }
}

void HEPulseShapeAnalyzer::analyze(const edm::Event& ev, const edm::EventSetup& es) {
  const HcalDbService* cond = &es.getData(db_);
  const HcalTimeSlew* timeSlew = &es.getData(timeSlewTok_);
  edm::Handle<QIE11DigiCollection> digis;
  ev.getByToken(tok_, digis);
  if (!digis.isValid()) return;

  for (auto raw : *digis) {
    QIE11DataFrame df(raw);
    HcalDetId did(df.id());

    int s;
    if (did.subdet() == HcalBarrel)      s = kHB;
    else if (did.subdet() == HcalEndcap) s = kHE;
    else continue;  // skip HF/HO/other — not part of this study

    const HcalQIECoder* cc = cond->getHcalCoder(did);
    const HcalQIEShape* sh = cond->getHcalShape(cc);
    HcalCoderDb coder(*cc, *sh);
    CaloSamples cs;
    coder.adc2fC(df, cs);

    // Per-capid pedestal subtraction — same as HBHEPhase1Reconstructor L573
    const HcalCalibrations& calib = cond->getHcalCalibrations(did);

    nsamp_ = df.samples();
    soi_   = df.presamples();

    // Replicate HBHEPhase1Reconstructor use8ts logic (use8ts=True, soiWanted=3):
    // shift the window so SOI lands at output bin 3, copy 8 TS.
    const int nOut     = (nsamp_ > 8) ? 8 : nsamp_;
    const int soiWanted = 3;
    const int tsShift  = (nsamp_ > 8)
        ? std::clamp(soi_ - soiWanted, 0, nsamp_ - nOut)
        : 0;

    q_.assign(nOut, 0.f);
    sumQ_ = 0.f;
    for (int copy = 0; copy < nOut; ++copy) {
      int hw    = copy + tsShift;
      int capid = df[hw].capid();
      q_[copy]  = cs[hw] - calib.pedestal(capid);
      sumQ_    += q_[copy];
    }

    // Delta_slew = HcalTimeSlew::delay(sumQ_, Medium) — the M2 time-slew
    // correction (see HcalTimeSlew.cc, Delta_slew = tzero + slope*ln(fC),
    // clamped to [0, tmax]). "Medium" matches the BiasSetting used for HB/HE
    // in reconstruction (HcalTimeSlew.h class comment / MahiFit slewFlavor_).
    // Filled here, BEFORE the qCut selection below, so timeSlewDelay_vs_sumQ
    // also covers the sub-qCut region and shows where the M2 correction
    // transitions from non-zero down to the clamped 0 ns floor — delay()
    // requires fC > 0 (log(fC) inside), so guard against sumQ_ <= 0.
    if (sumQ_ > 0.f) {
      timeSlewDelay_ = timeSlew->delay(sumQ_, HcalTimeSlew::Medium);
      timeSlewVsSumQ_[s]->Fill(sumQ_, timeSlewDelay_);
    }

    if (sumQ_ <= qcut_) continue;

    for (int copy = 0; copy < nOut; ++copy)
      prof_[s]->Fill(copy, q_[copy] / sumQ_);

    // 10-TS raw: sum over all hardware TS, no window shift, SOI at its hardware position
    float sumQ10 = 0.f;
    for (int ts = 0; ts < nsamp_; ++ts)
      sumQ10 += cs[ts] - calib.pedestal(df[ts].capid());
    if (sumQ10 > 0.f) {
      for (int ts = 0; ts < nsamp_; ++ts)
        prof10_[s]->Fill(ts, (cs[ts] - calib.pedestal(df[ts].capid())) / sumQ10);
    }

    ieta_=did.ieta(); iphi_=did.iphi(); depth_=did.depth();
    nsamp_ = nOut;
    tree_[s]->Fill();
  }
}
DEFINE_FWK_MODULE(HEPulseShapeAnalyzer);
