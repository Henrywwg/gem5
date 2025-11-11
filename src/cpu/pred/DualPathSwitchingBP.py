from m5.objects import BranchPredictor

class DualPathSwitchingBP(BranchPredictor):
    type = 'DualPathSwitchingBP'
    cxx_class = 'DualPathSwitchingBP'
    cxx_header = "cpu/pred/dual_path_switching_bp.hh"

    # parameters to tune from python
    windowSize = Param.Int(100, "Number of recent branches tracked")
    confidenceThreshold = Param.Float(0.85, "Confidence threshold to disable dual-path")
