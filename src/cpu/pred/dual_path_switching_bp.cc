#include "cpu/pred/dual_path_switching_bp.hh"
#include "base/trace.hh"

DualPathSwitchingBP::DualPathSwitchingBP(const Params *p)
    : BPredUnit(p), dualPathActive(false){
}

Addr
DualPathSwitchingBP::predict(ThreadID tid, Addr branch_addr, bool cond_branch){
    // call parent predictor
    Addr target = BPredUnit::predict(tid, branch_addr, cond_branch);

    float confidence = 0.8f; // placeholder for your real logic
    dualPathActive = shouldEnableDualPath(confidence);

    DPRINTF(Fetch, "Dual-path %s for branch at %#x\n",
            dualPathActive ? "enabled" : "disabled", branch_addr);

    return target;
}

bool
DualPathSwitchingBP::shouldEnableDualPath(float conf){
    return conf < 0.6; //
}
