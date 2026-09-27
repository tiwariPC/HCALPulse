// HEPulseShapeAnalyzer.cc
// Slide-18 MC side: HE QIE11, per-TS pedestal-subtracted charge fractions.
// Uses HcalCoderDb (same as reco) for ADC->fC, then subtracts per-capid pedestal.
// Applies the same use8ts logic as HBHEPhase1Reconstructor (use8ts=True default):
//   tsShift = clamp(soi - soiWanted, 0, nRead - 8),  soiWanted = 3
//   copies 8 TS starting at tsShift, so SOI always falls at output bin 3.
// TProfile output = mean charge fraction vs output TS (0-7, SOI at 3).

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

#include "TProfile.h"
#include "TH1F.h"
#include "TTree.h"
#include "TString.h"
#include <algorithm>
#include <vector>

class HEPulseShapeAnalyzer : public edm::one::EDAnalyzer<edm::one::SharedResources> {
public:
  explicit HEPulseShapeAnalyzer(const edm::ParameterSet&);
  void analyze(const edm::Event&, const edm::EventSetup&) override;
private:
  edm::EDGetTokenT<QIE11DigiCollection> tok_;
  edm::ESGetToken<HcalDbService, HcalDbRecord> db_;
  double qcut_;
  TProfile* prof_;
  TProfile* prof10_;
  TTree* tree_;
  int ieta_, iphi_, depth_, soi_, nsamp_;
  float sumQ_;
  std::vector<float> q_;
};

HEPulseShapeAnalyzer::HEPulseShapeAnalyzer(const edm::ParameterSet& ps)
  : tok_(consumes<QIE11DigiCollection>(ps.getParameter<edm::InputTag>("digiTag"))),
    db_(esConsumes<HcalDbService, HcalDbRecord>()),
    qcut_(ps.getParameter<double>("qCut")) {
  usesResource("TFileService");
  edm::Service<TFileService> fs;
  // 8 output TS (0-7), SOI at bin 3 — matches HBHEPhase1Reconstructor use8ts=True convention
  prof_ = fs->make<TProfile>("frac_vs_ts","HE_SiPM mean charge fraction;Time Slice;A.U.",8,-0.5,7.5);
  // 10 raw TS (0-9), no window shift — SOI stays at hardware presamples position (TS5 in Run-3 HE MC)
  prof10_ = fs->make<TProfile>("frac_vs_ts_10","HE_SiPM mean charge fraction (10 TS raw);Time Slice;A.U.",10,-0.5,9.5);
  tree_ = fs->make<TTree>("pulse","");
  tree_->Branch("ieta",&ieta_); tree_->Branch("iphi",&iphi_); tree_->Branch("depth",&depth_);
  tree_->Branch("soi",&soi_);  tree_->Branch("nsamp",&nsamp_); tree_->Branch("sumQ",&sumQ_);
  tree_->Branch("q",&q_);

  // Save shape 207 (siPMShapeData2018_, 2017 isotrack DATA LUT) and shape 208
  // (siPMShapeMCRecoRun3_, shape 206 + 7.2 ns shift, MC RECO LUT — not data)
  // directly from CMSSW, so plot_from_fc.py can read them from this ROOT
  // file instead of a hand-maintained text dump. HcalPulseShapes' no-arg
  // constructor needs no EventSetup/conditions — it precomputes all
  // hardcoded shapes (206/207/208/...) in its constructor body.
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
  edm::Handle<QIE11DigiCollection> digis;
  ev.getByToken(tok_, digis);
  if (!digis.isValid()) return;

  for (auto raw : *digis) {
    QIE11DataFrame df(raw);
    HcalDetId did(df.id());
    if (did.subdet() != HcalEndcap) continue;

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
    if (sumQ_ <= qcut_) continue;

    for (int copy = 0; copy < nOut; ++copy)
      prof_->Fill(copy, q_[copy] / sumQ_);

    // 10-TS raw: sum over all hardware TS, no window shift, SOI at its hardware position
    float sumQ10 = 0.f;
    for (int ts = 0; ts < nsamp_; ++ts)
      sumQ10 += cs[ts] - calib.pedestal(df[ts].capid());
    if (sumQ10 > 0.f) {
      for (int ts = 0; ts < nsamp_; ++ts)
        prof10_->Fill(ts, (cs[ts] - calib.pedestal(df[ts].capid())) / sumQ10);
    }

    ieta_=did.ieta(); iphi_=did.iphi(); depth_=did.depth();
    nsamp_ = nOut;
    tree_->Fill();
  }
}
DEFINE_FWK_MODULE(HEPulseShapeAnalyzer);
