// dual_path_switching_bp.hh
#include "cpu/pred/bpred_unit.hh"

class DualPathSwitchingBP : public BPredUnit
{
  public:
    DualPathSwitchingBP(const Params *p);

    Addr predict(ThreadID tid, Addr branch_addr, bool cond_branch) override;

    bool enableDualPath() const { return dualPathActive; }

  private:
    bool dualPathActive;
    bool shouldEnableDualPath(float confidence);
};
