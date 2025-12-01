# Copyright (c) 2024 The Regents of the University of Wisconsin-Madison
# All rights reserved.

from m5.params import *
from m5.SimObject import SimObject


class DualPathSwitcher(SimObject):
    type = "DualPathSwitcher"
    cxx_class = "gem5::o3::DualPathSwitcher"
    cxx_header = "cpu/o3/dual_path_switcher.hh"

    # Accuracy tracking window size
    window_size = Param.Unsigned(
        100, "Number of branches to track for accuracy"
    )

    # Threshold to switch from dual-path to single-path mode
    high_threshold = Param.Percent(
        85, "Accuracy threshold to switch to single-path (%)"
    )

    # Threshold to switch back to dual-path mode (hysteresis)
    low_threshold = Param.Percent(
        70, "Accuracy threshold to switch back to dual-path (%)"
    )

    # Start in dual-path mode
    initial_dual_path = Param.Bool(True, "Start in dual-path mode")

    # Alternate path fetch policy: "global" or "selective"
    fetch_policy = Param.String(
        "global",
        "Alternate path fetch policy: 'global' (all branches) or 'selective' (low-confidence only)",
    )

    # Confidence threshold for selective policy (0-100%)
    confidence_threshold = Param.Percent(
        95, "Confidence threshold for selective fetch policy (%)"
    )

    # Switching mode: "accuracy" or "confidence"
    switching_mode = Param.String(
        "accuracy",
        "Mode switching policy: 'accuracy' (use historical accuracy) or 'confidence' (use predictor confidence)",
    )
