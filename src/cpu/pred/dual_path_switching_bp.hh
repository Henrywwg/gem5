// dual_path_switching_bp.hh
#pragma once

#include "cpu/pred/bpred_unit.hh"
#include "base/types.hh"
#include "debug/Branch.hh"

#include <deque>

class DualPathSwitchingBP : public BPredUnit
{
  public:
    DualPathSwitchingBP(const Params *p);

    // predict returns the target address like other BPredUnit implementations
    Addr predict(ThreadID tid, Addr branch_addr, bool cond_branch) override;

    // update is called when branch resolution happens
    void update(ThreadID tid, Addr branch_addr, bool taken,
                bool mispred) override;

    // reset is called on context switch / CPU reset
    void reset(ThreadID tid) override;

    // expose current mode
    bool useDualPathMode() const { return use_dual_path_; }

  private:
    // internal helpers
    void recomputeConfidence();
    void maybeSwitchMode();

    // configuration
    const int window_size_;
    const double threshold_;

    // state
    std::deque<bool> history_; // ring of last outcomes (true=correct)
    double confidence_;        // cached computed confidence
    bool use_dual_path_;       // current mode: true => dual-path
};
