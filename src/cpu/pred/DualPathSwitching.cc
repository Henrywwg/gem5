/*
 * Copyright (c) 2022-2023 The University of Edinburgh
 * All rights reserved
 *
 * The license below extends only to copyright in the software and shall
 * not be construed as granting a license to any other intellectual
 * property including but not limited to intellectual property relating
 * to a hardware implementation of the functionality of the software
 * licensed hereunder.  You may use the software subject to the license
 * terms below provided that you ensure that this notice is replicated
 * unmodified and in its entirety in all distributions of the software,
 * modified or unmodified, in source code or in binary form.
 *
 * Copyright (c) 2014 The University of Wisconsin
 *
 * Copyright (c) 2006 INRIA (Institut National de Recherche en
 * Informatique et en Automatique  / French National Research Institute
 * for Computer Science and Applied Mathematics)
 *
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are
 * met: redistributions of source code must retain the above copyright
 * notice, this list of conditions and the following disclaimer;
 * redistributions in binary form must reproduce the above copyright
 * notice, this list of conditions and the following disclaimer in the
 * documentation and/or other materials provided with the distribution;
 * neither the name of the copyright holders nor the names of its
 * contributors may be used to endorse or promote products derived from
 * this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 * "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 * LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
 * A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
 * OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
 * SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
 * LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
 * DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
 * THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 * (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 * OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */

/* @file
 * Modification of L-tage predictor for ECE752 project.
 * Performs intelligent switching between dual path
 * execution and base tage predictor.
 */

#include "cpu/pred/DualPathSwitching.hh"

#include "base/intmath.hh"
#include "base/logging.hh"
#include "base/trace.hh"
#include "debug/Fetch.hh"

namespace gem5
{

namespace branch_prediction
{

    //Changes here to initialize our added flags and predictor accoutrement
DPSTAGE::DPSTAGE(const DPSTAGEParams &params)
  : TAGE(params),
  loopPredictor(nullptr),
  accuracyWindow(),
  accuracyWindowSize(100),
  correctCount(0),
  dualPathMode(true),
  threshold(0.7)
{
}

void
DPSTAGE::init()
{
    TAGE::init();
}

void
DPSTAGE::branchPlaceholder(ThreadID tid, Addr pc,
                         bool uncond, void * &bpHistory)
{
    DPSTAGEBranchInfo *bi = new DPSTAGEBranchInfo(*tage, *loopPredictor,
                                              pc, !uncond);
    bpHistory = (void*)(bi);
}

//prediction
bool
DPSTAGE::predict(ThreadID tid, Addr branch_pc, bool cond_branch, void* &b)
{
    DPSTAGEBranchInfo *bi = new DPSTAGEBranchInfo(*tage, *loopPredictor,
                                              branch_pc, cond_branch);
    b = (void*)(bi);

    //We just use the base tage predictor for comparison
    bool pred_taken = tage->tagePredict(tid, branch_pc, cond_branch,
                                        bi->tageBranchInfo);

    // record final prediction
    bi->lpBranchInfo->predTaken = pred_taken;

    return pred_taken;
}

// PREDICTOR UPDATE
void
DPSTAGE::update(ThreadID tid, Addr pc, bool taken, void * &bp_history,
              bool squashed, const StaticInstPtr & inst, Addr target)
{

    assert(bp_history);

    DPSTAGEBranchInfo* bi = static_cast<DPSTAGEBranchInfo*>(bp_history);

    // Get the original prediction and compare to actual result
    bool predicted_taken = bi->lpBranchInfo->predTaken;
    bool mispredicted = predicted_taken != taken;

    // Alright heres the juicy part :3
    // dequeue an item and if it was a correct pred, decrement appropriately
    if (accuracyWindow.size() >= accuracyWindowSize) {
        if (accuracyWindow.front()) correctCount--;
        accuracyWindow.pop_front();
    }

    //Add in the new value
    accuracyWindow.push_back(mispredicted);
    if (mispredicted) correctCount++;

    //Calculate our new accuracy and switch to SDPE
    double acc = static_cast<double>(correctCount) / accuracyWindow.size();
    dualPathMode = (acc < threshold);

    if (squashed) {
        if (tage->isSpeculativeUpdateEnabled()) {
            // This restores the global history, then update it
            // and recomputes the folded histories.
            tage->squash(tid, taken, target, inst, bi->tageBranchInfo);

            if (bi->tageBranchInfo->condBranch) {
                loopPredictor->squashLoop(bi->lpBranchInfo);
            }
        }
        return;
    }

    int nrand = rng->random<int>() & 3;
    if (bi->tageBranchInfo->condBranch) {
        // Update TAGE predictor for this branch
        tage->updateStats(taken, bi->tageBranchInfo);

        loopPredictor->updateStats(taken, bi->lpBranchInfo);

        loopPredictor->condBranchUpdate(tid, pc, taken,
            bi->tageBranchInfo->tagePred, bi->lpBranchInfo, instShiftAmt);

        tage->condBranchUpdate(tid, pc, taken, bi->tageBranchInfo,
            nrand, target, bi->lpBranchInfo->predTaken);
    }

    tage->updateHistories(tid, pc, false, taken, target,
                           inst, bi->tageBranchInfo);

    delete bi;
    bp_history = nullptr;
}

void
DPSTAGE::squash(ThreadID tid, void * &bp_history)
{
    DPSTAGEBranchInfo* bi = (DPSTAGEBranchInfo*)(bp_history);

    if (bi->tageBranchInfo->condBranch) {
        loopPredictor->squash(tid, bi->lpBranchInfo);
    }

    TAGE::squash(tid, bp_history);
}

} // namespace branch_prediction
} // namespace gem5
