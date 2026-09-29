// HBHEChannelInfoPulseAnalyzer.cc
// HBHEChannelInfo-based counterpart of HEPulseShapeAnalyzer: instead of
// hand-decoding QIE11DigiCollection (ADC->fC, pedestal, use8ts shift), it
// reads the HBHEChannelInfoCollection that HBHEPhase1Reconstructor produces
// when saveInfos=True. Every sample in it is exactly what Mahi sees:
//   - 8 TS with SOI at 3 (use8ts=True, same tsShift logic)
//   - tsCharge(ts) = rawCharge - pedestal (pedestal is the "effective" one,
//     incl. SiPM dark current, when saveEffectivePedestal=True — the Run-3 default)
//   - isDropped() = taggedBadByDb || dropByZS || badSOI  (HBHEPhase1Reconstructor
//     setChannelInfo), where dropByZS = dropZSmarkedPassed && frame.zsMarkAndPass().
// Run the reconstructor with saveDroppedInfos=True so dropped (mostly
// ZS-marked) channels are kept in the collection: they are profiled
// separately (frac_vs_ts_dropped_*) so the effect of the ZS flag is visible,
// and excluded from the main frac_vs_ts_* profiles when skipDropped=True.
// isDropped() cannot distinguish ZS from bad-by-DB/bad-SOI; ZS dominates.
//
// Histogram/tree names match HEPulseShapeAnalyzer, so plot_from_fc.py reads
// either one via --dir (TFileService directory = module label).

#include "FWCore/Framework/interface/one/EDAnalyzer.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/EventSetup.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/ServiceRegistry/interface/Service.h"
#include "CommonTools/UtilAlgos/interface/TFileService.h"

#include "DataFormats/HcalRecHit/interface/HBHEChannelInfo.h"
#include "DataFormats/HcalRecHit/interface/HcalRecHitCollections.h"
#include "DataFormats/HcalDetId/interface/HcalDetId.h"

#include "CalibCalorimetry/HcalAlgos/interface/HcalPulseShapes.h"
#include "CalibCalorimetry/HcalAlgos/interface/HcalTimeSlew.h"
#include "CondFormats/DataRecord/interface/HcalTimeSlewRecord.h"

#include "TProfile.h"
#include "TH1F.h"
#include "TH1D.h"
#include "TH2F.h"
#include "TTree.h"
#include <cmath>
#include <vector>

namespace {
  enum SubdetIdx { kHB = 0, kHE = 1, kNSubdet = 2 };
  const char* subdetName[kNSubdet] = {"HB", "HE"};
  // nChan_* bin labels (1-based bins)
  enum CountBin { kAll = 1, kDropped, kPassQ, kPassQNotDropped };
}

class HBHEChannelInfoPulseAnalyzer : public edm::one::EDAnalyzer<edm::one::SharedResources> {
public:
  explicit HBHEChannelInfoPulseAnalyzer(const edm::ParameterSet&);
  void analyze(const edm::Event&, const edm::EventSetup&) override;
private:
  edm::EDGetTokenT<HBHEChannelInfoCollection> tok_;
  edm::ESGetToken<HcalTimeSlew, HcalTimeSlewRecord> timeSlewTok_;
  double qcut_;
  bool skipDropped_;
  TProfile* prof_[kNSubdet];
  TProfile* profDropped_[kNSubdet];
  TH1D* nChan_[kNSubdet];  // TH1D: channel counts exceed float precision (2^24)
  TH2F* timeSlewVsSumQ_[kNSubdet];
  TTree* tree_[kNSubdet];
  int ieta_, iphi_, depth_, soi_, nsamp_, recoShape_;
  bool dropped_;
  float sumQ_, energy_, timeSlewDelay_;
  std::vector<float> q_;
};

HBHEChannelInfoPulseAnalyzer::HBHEChannelInfoPulseAnalyzer(const edm::ParameterSet& ps)
  : tok_(consumes<HBHEChannelInfoCollection>(ps.getParameter<edm::InputTag>("infoTag"))),
    timeSlewTok_(esConsumes<HcalTimeSlew, HcalTimeSlewRecord>(edm::ESInputTag("", "HBHE"))),
    qcut_(ps.getParameter<double>("qCut")),
    skipDropped_(ps.getParameter<bool>("skipDropped")) {
  usesResource("TFileService");
  edm::Service<TFileService> fs;

  for (int s = 0; s < kNSubdet; ++s) {
    const char* sd = subdetName[s];
    prof_[s] = fs->make<TProfile>(Form("frac_vs_ts_%s", sd),
        Form("%s_SiPM mean charge fraction (HBHEChannelInfo);Time Slice;A.U.", sd), 8, -0.5, 7.5);
    profDropped_[s] = fs->make<TProfile>(Form("frac_vs_ts_dropped_%s", sd),
        Form("%s_SiPM mean charge fraction, isDropped() (ZS-marked/bad) channels;Time Slice;A.U.", sd),
        8, -0.5, 7.5);
    nChan_[s] = fs->make<TH1D>(Form("nChan_%s", sd), Form("%s channel counts;;Channels", sd), 4, 0.5, 4.5);
    nChan_[s]->GetXaxis()->SetBinLabel(kAll, "all");
    nChan_[s]->GetXaxis()->SetBinLabel(kDropped, "dropped");
    nChan_[s]->GetXaxis()->SetBinLabel(kPassQ, "sumQ>qCut");
    nChan_[s]->GetXaxis()->SetBinLabel(kPassQNotDropped, "sumQ>qCut && !dropped");

    // Same log-x binning as HEPulseShapeAnalyzer
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
    tree_[s]->Branch("dropped",&dropped_);
    tree_[s]->Branch("recoShape",&recoShape_);
    tree_[s]->Branch("energy",&energy_);
  }

  // shape 207 = data LUT (siPMShapeData2018_), shape 208 = MC reco LUT
  // (siPMShapeMCRecoRun3_, NOT data) — same as HEPulseShapeAnalyzer.
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

void HBHEChannelInfoPulseAnalyzer::analyze(const edm::Event& ev, const edm::EventSetup& es) {
  const HcalTimeSlew* timeSlew = &es.getData(timeSlewTok_);
  edm::Handle<HBHEChannelInfoCollection> infos;
  ev.getByToken(tok_, infos);
  if (!infos.isValid()) return;

  for (const HBHEChannelInfo& info : *infos) {
    const HcalDetId did(info.id());
    int s;
    if (did.subdet() == HcalBarrel)      s = kHB;
    else if (did.subdet() == HcalEndcap) s = kHE;
    else continue;

    const unsigned nTS = info.nSamples();
    dropped_ = info.isDropped();
    nChan_[s]->Fill(kAll);
    if (dropped_) nChan_[s]->Fill(kDropped);

    q_.assign(nTS, 0.f);
    for (unsigned ts = 0; ts < nTS; ++ts)
      q_[ts] = info.tsCharge(ts);
    sumQ_ = info.chargeInWindow(0, nTS);

    // M2 time-slew delay, filled before the qCut (see HEPulseShapeAnalyzer);
    // delay() takes log(fC), so require sumQ_ > 0. Dropped channels are kept
    // out of the histogram when skipDropped, like every other main output.
    timeSlewDelay_ = 0.f;
    if (sumQ_ > 0.f) {
      timeSlewDelay_ = timeSlew->delay(sumQ_, HcalTimeSlew::Medium);
      if (!(dropped_ && skipDropped_))
        timeSlewVsSumQ_[s]->Fill(sumQ_, timeSlewDelay_);
    }

    if (sumQ_ <= qcut_) continue;
    nChan_[s]->Fill(kPassQ);

    if (dropped_) {
      for (unsigned ts = 0; ts < nTS; ++ts)
        profDropped_[s]->Fill(ts, q_[ts] / sumQ_);
      if (skipDropped_) continue;
    } else {
      nChan_[s]->Fill(kPassQNotDropped);
    }

    for (unsigned ts = 0; ts < nTS; ++ts)
      prof_[s]->Fill(ts, q_[ts] / sumQ_);

    ieta_ = did.ieta(); iphi_ = did.iphi(); depth_ = did.depth();
    soi_ = info.soi(); nsamp_ = nTS; recoShape_ = info.recoShape();
    energy_ = info.energyInWindow(0, nTS);
    tree_[s]->Fill();
  }
}
DEFINE_FWK_MODULE(HBHEChannelInfoPulseAnalyzer);
