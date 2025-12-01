# Copyright (c) 2025 The Regents of the University of Wisconsin-Madison
# All rights reserved.

from m5.objects.BranchPredictor import TAGE
from m5.params import *


class DPSTAGE(TAGE):
    type = "DPSTAGE"
    cxx_class = "gem5::branch_prediction::DPSTAGE"
    cxx_header = "cpu/pred/DualPathSwitching.hh"

    # Inherits all TAGE parameters
    # Additional parameters for dual-path switching can be added here if needed
