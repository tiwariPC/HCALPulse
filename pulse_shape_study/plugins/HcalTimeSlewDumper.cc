// HcalTimeSlewDumper.cc
// Retrieves the HcalTimeSlew conditions payload (time-slew / TimeSlew effect
// correction) from the DB via EventSetup and prints it, for the HBHE label
// used by SimpleHBHEPhase1Algo/MahiFit (see
// RecoLocalCalo/HcalRecAlgos/src/SimpleHBHEPhase1Algo.cc, MahiFit.cc L29/274).
// This is a read-only diagnostic — no reconstruction logic here.
//
// Prints, once at beginRun():
//   - delay(fC, BiasSetting) for a few representative charges, all three
//     BiasSettings (Slow/Medium/Fast) — the M2 parametrization overload,
//     which is what MahiFit::updatePulseShape() actually calls.
//   - delay(fC, ParaSource, BiasSetting, isHPD) for the same charges with
//     ParaSource::HBHE — the M3 parametrization overload.

#include "FWCore/Framework/interface/one/EDAnalyzer.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/EventSetup.h"
#include "FWCore/Framework/interface/Run.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/MessageLogger/interface/MessageLogger.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/Utilities/interface/ESInputTag.h"

#include "CalibCalorimetry/HcalAlgos/interface/HcalTimeSlew.h"
#include "CondFormats/DataRecord/interface/HcalTimeSlewRecord.h"

class HcalTimeSlewDumper : public edm::one::EDAnalyzer<edm::one::WatchRuns> {
public:
  explicit HcalTimeSlewDumper(const edm::ParameterSet&);
  void analyze(const edm::Event&, const edm::EventSetup&) override {}
  void beginRun(const edm::Run&, const edm::EventSetup&) override;
  void endRun(const edm::Run&, const edm::EventSetup&) override {}

private:
  edm::ESGetToken<HcalTimeSlew, HcalTimeSlewRecord> tok_;
  std::string label_;
};

HcalTimeSlewDumper::HcalTimeSlewDumper(const edm::ParameterSet& ps)
    : tok_(esConsumes<HcalTimeSlew, HcalTimeSlewRecord, edm::Transition::BeginRun>(
          edm::ESInputTag("", ps.getParameter<std::string>("label")))),
      label_(ps.getParameter<std::string>("label")) {}

void HcalTimeSlewDumper::beginRun(const edm::Run&, const edm::EventSetup& es) {
  const HcalTimeSlew* ts = &es.getData(tok_);

  const float testCharges[] = {1.f, 5.f, 20.f, 100.f, 1000.f};
  const HcalTimeSlew::BiasSetting biases[] = {
      HcalTimeSlew::Slow, HcalTimeSlew::Medium, HcalTimeSlew::Fast};
  const char* biasNames[] = {"Slow", "Medium", "Fast"};

  edm::LogSystem("HcalTimeSlewDumper")
      << "=== HcalTimeSlew (label=\"" << label_ << "\") ===";

  // M2 overload: float delay(float fC, BiasSetting bias = Medium) const
  // — this is what MahiFit::updatePulseShape() calls.
  for (float q : testCharges) {
    for (int b = 0; b < 3; ++b) {
      edm::LogSystem("HcalTimeSlewDumper")
          << "  M2 delay(fC=" << q << ", bias=" << biasNames[b]
          << ") = " << ts->delay(q, biases[b]) << " ns";
    }
  }

  // M3 overload: double delay(double fC, ParaSource source, BiasSetting bias, bool isHPD) const
  for (float q : testCharges) {
    for (int b = 0; b < 3; ++b) {
      edm::LogSystem("HcalTimeSlewDumper")
          << "  M3 delay(fC=" << q << ", source=HBHE, bias=" << biasNames[b]
          << ", isHPD=true) = "
          << ts->delay(double(q), HcalTimeSlew::HBHE, biases[b], true) << " ns";
      edm::LogSystem("HcalTimeSlewDumper")
          << "  M3 delay(fC=" << q << ", source=HBHE, bias=" << biasNames[b]
          << ", isHPD=false [SiPM]) = "
          << ts->delay(double(q), HcalTimeSlew::HBHE, biases[b], false) << " ns";
    }
  }
}

DEFINE_FWK_MODULE(HcalTimeSlewDumper);
