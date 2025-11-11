// dual_path_switching_bp.cc
#include "cpu/pred/dual_path_switching_bp.hh"
#include "base/trace.hh"

DualPathSwitchingBP::DualPathSwitchingBP(const Params *p)
    : BPredUnit(p),
      window_size_(p->windowSize),
      threshold_(p->confidenceThreshold),
      confidence_(0.0),
      use_dual_path_(true) // start in dual-path mode
{
    DPRINTF(Branch, "DualPathSwitchingBP constructed: window=%d thr=%.2f\n",
            window_size_, threshold_);
}

Addr
DualPathSwitchingBP::predict(ThreadID tid, Addr branch_addr, bool cond_branch)
{
    // Delegate to the base class prediction logic for the actual target.
    Addr target = BPredUnit::predict(tid, branch_addr, cond_branch);

    // If we have no history we stay in dual-path (safe default).
    if (history_.empty()) {
        use_dual_path_ = true;
        DPRINTF(Branch, "No history -> dual-path for %#x\n", branch_addr);
    } else {
        // For logging / debug, recompute and maybe switch mode
        recomputeConfidence();
        maybeSwitchMode();
    }

    DPRINTF(Branch, "Predict for %#x -> target %#x dual=%d conf=%.2f\n",
            branch_addr, target, use_dual_path_, confidence_);

    return target;
}

void
DualPathSwitchingBP::update(ThreadID tid, Addr branch_addr, bool taken,
                            bool mispred)
{
    // correct = not mispred
    bool correct = !mispred;

    // push the latest outcome
    history_.push_back(correct);
    if ((int)history_.size() > window_size_)
        history_.pop_front();

    // recompute confidence and maybe switch mode
    recomputeConfidence();
    maybeSwitchMode();

    DPRINTF(Branch, "Update for %#x -> correct=%d conf=%.2f dual=%d\n",
            branch_addr, correct, confidence_, use_dual_path_);

    // Also call base class update to keep other predictor state coherent
    BPredUnit::update(tid, branch_addr, taken, mispred);
}

void
DualPathSwitchingBP::reset(ThreadID tid)
{
    // context switch or CPU reset: clear history and force dual-path
    history_.clear();
    confidence_ = 0.0;
    use_dual_path_ = true;

    DPRINTF(Branch, "Reset on thread %d -> cleared history, dual-path enabled\n",
            tid);

    // let base class handle its own reset bookkeeping
    BPredUnit::reset(tid);
}

void
DualPathSwitchingBP::recomputeConfidence()
{
    if (history_.empty()) {
        confidence_ = 0.0;
        return;
    }

    int correct = 0;
    for (bool b : history_)
        correct += b ? 1 : 0;

    confidence_ = static_cast<double>(correct) / history_.size();
}

void
DualPathSwitchingBP::maybeSwitchMode()
{
    // If confidence is above threshold, disable dual-path
    if (confidence_ >= threshold_) {
        if (use_dual_path_) {
            DPRINTF(Branch, "Confidence %.2f >= %.2f -> disable dual-path\n",
                    confidence_, threshold_);
        }
        use_dual_path_ = false;
    } else {
        if (!use_dual_path_) {
            DPRINTF(Branch, "Confidence %.2f < %.2f -> enable dual-path\n",
                    confidence_, threshold_);
        }
        use_dual_path_ = true;
    }
}
