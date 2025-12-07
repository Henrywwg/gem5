/*
 * Copyright (c) 2010-2014 ARM Limited
 * Copyright (c) 2012-2013 AMD
 * All rights reserved.
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
 * Copyright (c) 2004-2006 The Regents of The University of Michigan
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

#include "cpu/o3/fetch.hh"

#include <algorithm>
#include <cstring>
#include <list>
#include <map>
#include <queue>

#include "arch/generic/tlb.hh"
#include "base/types.hh"
#include "cpu/base.hh"
#include "cpu/exetrace.hh"
#include "cpu/nop_static_inst.hh"
#include "cpu/o3/cpu.hh"
#include "cpu/o3/dyn_inst.hh"
#include "cpu/o3/limits.hh"
#include "debug/Activity.hh"
#include "debug/Drain.hh"
#include "debug/Fetch.hh"
#include "debug/O3CPU.hh"
#include "debug/O3PipeView.hh"
#include "mem/packet.hh"
#include "params/BaseO3CPU.hh"
#include "sim/byteswap.hh"
#include "sim/core.hh"
#include "sim/eventq.hh"
#include "sim/full_system.hh"
#include "sim/system.hh"

namespace gem5
{

namespace o3
{

// Define static const members for realistic hardware constraints
const unsigned Fetch::APB_READ_LATENCY_CYCLES;
const unsigned Fetch::MAX_OUTSTANDING_ALT_FETCHES;
const unsigned Fetch::APB_WRITE_LATENCY_CYCLES;

Fetch::IcachePort::IcachePort(Fetch *_fetch, CPU *_cpu) :
        RequestPort(_cpu->name() + ".icache_port"), fetch(_fetch)
{}


Fetch::Fetch(CPU *_cpu, const BaseO3CPUParams &params)
    : fetchPolicy(params.smtFetchPolicy),
      cpu(_cpu),
      branchPred(nullptr),
      decodeToFetchDelay(params.decodeToFetchDelay),
      renameToFetchDelay(params.renameToFetchDelay),
      iewToFetchDelay(params.iewToFetchDelay),
      commitToFetchDelay(params.commitToFetchDelay),
      fetchWidth(params.fetchWidth),
      decodeWidth(params.decodeWidth),
      retryPkt(NULL),
      retryTid(InvalidThreadID),
      cacheBlkSize(cpu->cacheLineSize()),
      fetchBufferSize(params.fetchBufferSize),
      fetchBufferMask(fetchBufferSize - 1),
      fetchQueueSize(params.fetchQueueSize),
      numThreads(params.numThreads),
      numFetchingThreads(params.smtNumFetchingThreads),
      icachePort(this, _cpu),
      finishTranslationEvent(this), fetchStats(_cpu, this)
{
    if (numThreads > MaxThreads)
        fatal("numThreads (%d) is larger than compiled limit (%d),\n"
              "\tincrease MaxThreads in src/cpu/o3/limits.hh\n",
              numThreads, static_cast<int>(MaxThreads));
    if (fetchWidth > MaxWidth)
        fatal("fetchWidth (%d) is larger than compiled limit (%d),\n"
             "\tincrease MaxWidth in src/cpu/o3/limits.hh\n",
             fetchWidth, static_cast<int>(MaxWidth));
    if (fetchBufferSize > cacheBlkSize)
        fatal("fetch buffer size (%u bytes) is greater than the cache "
              "block size (%u bytes)\n", fetchBufferSize, cacheBlkSize);
    if (cacheBlkSize % fetchBufferSize)
        fatal("cache block (%u bytes) is not a multiple of the "
              "fetch buffer (%u bytes)\n", cacheBlkSize, fetchBufferSize);

    for (int i = 0; i < MaxThreads; i++) {
        fetchStatus[i] = Idle;
        decoder[i] = nullptr;
        pc[i].reset(params.isa[0]->newPCState());
        fetchOffset[i] = 0;
        macroop[i] = nullptr;
        delayedCommit[i] = false;
        memReq[i] = nullptr;
        stalls[i] = {false, false};
        fetchBuffer[i] = NULL;
        fetchBufferPC[i] = 0;
        fetchBufferValid[i] = false;
        lastIcacheStall[i] = 0;
        issuePipelinedIfetch[i] = false;
        squashStartTick[i] = 0;
        squashIsBranchMisp[i] = false;
        apbReadyTick[i] = 0;
        pendingApbAddr[i] = 0;
    }

    branchPred = params.branchPred;

    // Initialize I-cache filter setting
    icacheFilterEnabled = params.icacheFilterEnabled;
    DPRINTF(Fetch, "I-cache filter for APB inserts: %s\n",
            icacheFilterEnabled ? "enabled" : "disabled");

    for (ThreadID tid = 0; tid < numThreads; tid++) {
        decoder[tid] = params.decoder[tid];
        // Create space to buffer the cache line data,
        // which may not hold the entire cache line.
        fetchBuffer[tid] = new uint8_t[fetchBufferSize];
    }
    // --- APB initialization ---
    if (_cpu->apb) {
        apb = _cpu->apb;
    }
    // Get the size of an instruction.
    instSize = decoder[0]->moreBytesSize();
}

std::string Fetch::name() const { return cpu->name() + ".fetch"; }

void
Fetch::regProbePoints()
{
    ppFetch = new ProbePointArg<DynInstPtr>(cpu->getProbeManager(), "Fetch");
    ppFetchRequestSent = new ProbePointArg<RequestPtr>(cpu->getProbeManager(),
                                                       "FetchRequest");

}

Fetch::FetchStatGroup::FetchStatGroup(CPU *cpu, Fetch *fetch)
    : statistics::Group(cpu, "fetch"),
    ADD_STAT(predictedBranches, statistics::units::Count::get(),
             "Number of branches that fetch has predicted taken"),
    ADD_STAT(cycles, statistics::units::Cycle::get(),
             "Number of cycles fetch has run and was not squashing or "
             "blocked"),
    ADD_STAT(squashCycles, statistics::units::Cycle::get(),
             "Number of cycles fetch has spent squashing"),
    ADD_STAT(tlbCycles, statistics::units::Cycle::get(),
             "Number of cycles fetch has spent waiting for tlb"),
    ADD_STAT(idleCycles, statistics::units::Cycle::get(),
             "Number of cycles fetch was idle"),
    ADD_STAT(blockedCycles, statistics::units::Cycle::get(),
             "Number of cycles fetch has spent blocked"),
    ADD_STAT(miscStallCycles, statistics::units::Cycle::get(),
             "Number of cycles fetch has spent waiting on interrupts, or bad "
             "addresses, or out of MSHRs"),
    ADD_STAT(pendingDrainCycles, statistics::units::Cycle::get(),
             "Number of cycles fetch has spent waiting on pipes to drain"),
    ADD_STAT(noActiveThreadStallCycles, statistics::units::Cycle::get(),
             "Number of stall cycles due to no active thread to fetch from"),
    ADD_STAT(pendingTrapStallCycles, statistics::units::Cycle::get(),
             "Number of stall cycles due to pending traps"),
    ADD_STAT(pendingQuiesceStallCycles, statistics::units::Cycle::get(),
             "Number of stall cycles due to pending quiesce instructions"),
    ADD_STAT(icacheWaitRetryStallCycles, statistics::units::Cycle::get(),
             "Number of stall cycles due to full MSHR"),
    ADD_STAT(cacheLines, statistics::units::Count::get(),
             "Number of cache lines fetched"),
    ADD_STAT(icacheSquashes, statistics::units::Count::get(),
             "Number of outstanding Icache misses that were squashed"),
    ADD_STAT(tlbSquashes, statistics::units::Count::get(),
             "Number of outstanding ITLB misses that were squashed"),
    ADD_STAT(nisnDist, statistics::units::Count::get(),
             "Number of instructions fetched each cycle (Total)"),
    ADD_STAT(idleRate, statistics::units::Ratio::get(),
             "Ratio of cycles fetch was idle",
             idleCycles / cpu->baseStats.numCycles),
    ADD_STAT(altPathFetchRequests, statistics::units::Count::get(),
             "Number of alternate path fetch requests initiated"),
    ADD_STAT(altPathFetchCompleted, statistics::units::Count::get(),
             "Number of alternate path fetches completed"),
    ADD_STAT(altPathFetchSquashed, statistics::units::Count::get(),
             "Number of alternate path fetches squashed"),
    ADD_STAT(altPathCacheLines, statistics::units::Count::get(),
             "Number of cache lines fetched for alternate paths"),
    ADD_STAT(altPathBypassedIcache, statistics::units::Count::get(),
             "Number of alternate path fetches that bypassed I-cache fill (first fetch)"),
    ADD_STAT(altPathPromotedToIcache, statistics::units::Count::get(),
             "Number of alternate path fetches promoted to I-cache (repeat fetch)"),
    ADD_STAT(altPathFetchDeferred, statistics::units::Count::get(),
             "Number of alternate path fetches deferred due to cache blocked"),
    ADD_STAT(altPathFetchDeferredProcessed, statistics::units::Count::get(),
             "Number of deferred alternate path fetches processed"),
    ADD_STAT(altPathFetchDeferredDropped, statistics::units::Count::get(),
             "Number of deferred alternate path fetches dropped (queue full)"),
    ADD_STAT(altPathFetchMshrFull, statistics::units::Count::get(),
             "Number of alternate path fetches dropped due to MSHR limit"),
    ADD_STAT(apbWritePortContentions, statistics::units::Count::get(),
             "Number of times APB write port was busy (contention)"),
    ADD_STAT(apbWritePortStallCycles, statistics::units::Count::get(),
             "Total cycles stalled waiting for APB write port"),
    ADD_STAT(branchMispredRecoveryCycles, statistics::units::Cycle::get(),
             "Total cycles spent recovering from branch mispredictions"),
    ADD_STAT(apbRecoveryHits, statistics::units::Count::get(),
             "Number of branch mispredictions where APB had correct path"),
    ADD_STAT(apbRecoveryMisses, statistics::units::Count::get(),
             "Number of branch mispredictions where APB missed"),
    ADD_STAT(recoveryLatency, statistics::units::Cycle::get(),
             "Distribution of branch misprediction recovery latency"),
    ADD_STAT(apbHitRecoveryLatency, statistics::units::Cycle::get(),
             "Recovery latency when APB has correct path"),
    ADD_STAT(apbMissRecoveryLatency, statistics::units::Cycle::get(),
             "Recovery latency when APB misses"),
    ADD_STAT(altPathSkippedInIcache, statistics::units::Count::get(),
             "Alternate paths skipped because already in I-cache (easy cases)"),
    ADD_STAT(altPathInsertedHardCase, statistics::units::Count::get(),
             "Alternate paths inserted into APB (hard cases - not in I-cache)"),
    ADD_STAT(altPathRaceConditionMisses, statistics::units::Count::get(),
             "Race condition: path was in I-cache at insert but evicted before recovery"),
    ADD_STAT(icacheAccessesDuringRecovery, statistics::units::Count::get(),
             "I-cache accesses initiated during misprediction recovery"),
    ADD_STAT(icacheMissesDuringRecovery, statistics::units::Count::get(),
             "I-cache misses that completed during misprediction recovery")
{
        predictedBranches
            .prereq(predictedBranches);
        cycles
            .prereq(cycles);
        squashCycles
            .prereq(squashCycles);
        tlbCycles
            .prereq(tlbCycles);
        idleCycles
            .prereq(idleCycles);
        blockedCycles
            .prereq(blockedCycles);
        cacheLines
            .prereq(cacheLines);
        miscStallCycles
            .prereq(miscStallCycles);
        pendingDrainCycles
            .prereq(pendingDrainCycles);
        noActiveThreadStallCycles
            .prereq(noActiveThreadStallCycles);
        pendingTrapStallCycles
            .prereq(pendingTrapStallCycles);
        pendingQuiesceStallCycles
            .prereq(pendingQuiesceStallCycles);
        icacheWaitRetryStallCycles
            .prereq(icacheWaitRetryStallCycles);
        icacheSquashes
            .prereq(icacheSquashes);
        tlbSquashes
            .prereq(tlbSquashes);
        nisnDist
            .init(/* base value */ 0,
              /* last value */ fetch->fetchWidth,
              /* bucket size */ 1)
            .flags(statistics::pdf);
        idleRate
            .prereq(idleRate);
        recoveryLatency
            .init(/* base */ 0, /* max */ 1000, /* bucket size */ 10)
            .flags(statistics::pdf);
        apbHitRecoveryLatency
            .init(/* base */ 0, /* max */ 1000, /* bucket size */ 10)
            .flags(statistics::pdf);
        apbMissRecoveryLatency
            .init(/* base */ 0, /* max */ 1000, /* bucket size */ 10)
            .flags(statistics::pdf);
}
void
Fetch::setTimeBuffer(TimeBuffer<TimeStruct> *time_buffer)
{
    timeBuffer = time_buffer;

    // Create wires to get information from proper places in time buffer.
    fromDecode = timeBuffer->getWire(-decodeToFetchDelay);
    fromRename = timeBuffer->getWire(-renameToFetchDelay);
    fromIEW = timeBuffer->getWire(-iewToFetchDelay);
    fromCommit = timeBuffer->getWire(-commitToFetchDelay);
}

void
Fetch::setActiveThreads(std::list<ThreadID> *at_ptr)
{
    activeThreads = at_ptr;
}

void
Fetch::setFetchQueue(TimeBuffer<FetchStruct> *ftb_ptr)
{
    // Create wire to write information to proper place in fetch time buf.
    toDecode = ftb_ptr->getWire(0);
}

void
Fetch::startupStage()
{
    assert(priorityList.empty());
    resetStage();

    // Fetch needs to start fetching instructions at the very beginning,
    // so it must start up in active state.
    switchToActive();
}

void
Fetch::clearStates(ThreadID tid)
{
    fetchStatus[tid] = Running;
    set(pc[tid], cpu->pcState(tid));
    fetchOffset[tid] = 0;
    macroop[tid] = NULL;
    delayedCommit[tid] = false;
    memReq[tid] = NULL;
    stalls[tid].decode = false;
    stalls[tid].drain = false;
    fetchBufferPC[tid] = 0;
    fetchBufferValid[tid] = false;
    fetchQueue[tid].clear();

    // TODO not sure what to do with priorityList for now
    // priorityList.push_back(tid);

    // Clear out any of this thread's instructions being sent to decode.
    for (int i = -cpu->fetchQueue.getPast();
         i <= cpu->fetchQueue.getFuture(); ++i) {
        FetchStruct& fetch_struct = cpu->fetchQueue[i];
        removeCommThreadInsts(tid, fetch_struct);
    }
}

void
Fetch::resetStage()
{
    numInst = 0;
    interruptPending = false;
    cacheBlocked = false;

    priorityList.clear();

    // Setup PC and nextPC with initial state.
    for (ThreadID tid = 0; tid < numThreads; ++tid) {
        fetchStatus[tid] = Running;
        set(pc[tid], cpu->pcState(tid));
        fetchOffset[tid] = 0;
        macroop[tid] = NULL;

        delayedCommit[tid] = false;
        memReq[tid] = NULL;

        stalls[tid].decode = false;
        stalls[tid].drain = false;

        fetchBufferPC[tid] = 0;
        fetchBufferValid[tid] = false;

        fetchQueue[tid].clear();

        priorityList.push_back(tid);
    }

    wroteToTimeBuffer = false;
    _status = Inactive;
}

void
Fetch::processCacheCompletion(PacketPtr pkt)
{
    ThreadID tid = cpu->contextToThread(pkt->req->contextId());

    DPRINTF(Fetch, "[tid:%i] Waking up from cache miss.\n", tid);
    assert(!cpu->switchedOut());

    // Check if this is an alternate path fetch response
    Addr addr = pkt->req->getVaddr();
    Addr alignedPC = fetchBufferAlignPC(addr);
    auto it = outstandingAltFetches.find(alignedPC);

    if (it != outstandingAltFetches.end()) {
        // This is an alternate path fetch - insert into APB
        const uint8_t *data = pkt->getConstPtr<uint8_t>();
        if (apb) {
            apb->insertLine(alignedPC, data, fetchBufferSize);
            DPRINTF(Fetch, "[APB] Inserted alternate path line %#x into APB\n", alignedPC);
        }

        // Track alternate path fetch completion
        ++fetchStats.altPathFetchCompleted;
        ++fetchStats.altPathCacheLines;

        // REALISTIC HARDWARE: Model APB write port contention
        Tick writeStartTick = curTick();
        if (apbWritePortBusyUntil > curTick()) {
            // APB write port is busy, must wait
            Tick stallCycles = (apbWritePortBusyUntil - curTick()) / 1000;
            writeStartTick = apbWritePortBusyUntil;
            DPRINTF(Fetch, "[APB] Write port busy, delaying write by %d cycles\n",
                    stallCycles);
            ++fetchStats.apbWritePortContentions;
            fetchStats.apbWritePortStallCycles += stallCycles;
        }
        // Reserve APB write port
        apbWritePortBusyUntil = writeStartTick + (APB_WRITE_LATENCY_CYCLES * 1000);

        // Remove from tracking structures
        outstandingAltFetches.erase(it);
        altPathTranslations.erase(alignedPC);

        // Clean up and return - this is not a normal fetch
        delete pkt;
        return;
    }

    // Only change the status if it's still waiting on the icache access
    // to return.
    if (fetchStatus[tid] != IcacheWaitResponse ||
        pkt->req != memReq[tid]) {
        ++fetchStats.icacheSquashes;
        delete pkt;
        return;
    }

    memcpy(fetchBuffer[tid], pkt->getConstPtr<uint8_t>(), fetchBufferSize);
    fetchBufferValid[tid] = true;

    // Update I-cache tracking (for filtering APB inserts)
    updateRecentlyFetched(pkt->req->getVaddr());

    // Wake up the CPU (if it went to sleep and was waiting on
    // this completion event).
    cpu->wakeCPU();

    DPRINTF(Activity, "[tid:%i] Activating fetch due to cache completion\n",
            tid);

    switchToActive();

    // Track recovery completion for branch mispredictions
    if (squashIsBranchMisp[tid] && squashStartTick[tid] > 0) {
        Tick recoveryTime = curTick() - squashStartTick[tid];
        ++fetchStats.apbRecoveryMisses;
        ++fetchStats.icacheMissesDuringRecovery;  // This IS an I-cache miss during recovery
        fetchStats.apbMissRecoveryLatency.sample(recoveryTime);
        fetchStats.recoveryLatency.sample(recoveryTime);
        fetchStats.branchMispredRecoveryCycles += recoveryTime;
        
        // RACE CONDITION DETECTION: Check if we skipped this address
        // because it was in I-cache at insert time, but now we had
        // to fetch it from I-cache (meaning it was evicted and re-fetched)
        Addr recoveryAddr = fetchBufferAlignPC(memReq[tid]->getVaddr());
        if (skippedBecauseInIcache.find(recoveryAddr) != skippedBecauseInIcache.end()) {
            // This address was skipped at insert time because it was in I-cache
            // But now we're fetching it for recovery - means it got evicted!
            ++fetchStats.altPathRaceConditionMisses;
            DPRINTF(Fetch, "[tid:%i] RACE CONDITION DETECTED: addr %#x was in I-cache "
                    "at insert time but got evicted before recovery. Latency: %d cycles\n",
                    tid, recoveryAddr, recoveryTime);
            // Remove from tracking set
            skippedBecauseInIcache.erase(recoveryAddr);
        }
        
        DPRINTF(Fetch, "[tid:%i] APB miss for recovery. Latency: %d cycles\n",
                tid, recoveryTime);
        squashStartTick[tid] = 0;
        squashIsBranchMisp[tid] = false;
    }

    // Only switch to IcacheAccessComplete if we're not stalled as well.
    if (checkStall(tid)) {
        fetchStatus[tid] = Blocked;
    } else {
        fetchStatus[tid] = IcacheAccessComplete;
    }

    pkt->req->setAccessLatency();
    cpu->ppInstAccessComplete->notify(pkt);
    // Reset the mem req to NULL.
    delete pkt;
    memReq[tid] = NULL;
}

void
Fetch::drainResume()
{
    for (ThreadID i = 0; i < numThreads; ++i) {
        stalls[i].decode = false;
        stalls[i].drain = false;
    }
}

void
Fetch::drainSanityCheck() const
{
    assert(isDrained());
    assert(retryPkt == NULL);
    assert(retryTid == InvalidThreadID);
    assert(!cacheBlocked);
    assert(!interruptPending);

    for (ThreadID i = 0; i < numThreads; ++i) {
        assert(!memReq[i]);
        assert(fetchStatus[i] == Idle || stalls[i].drain);
    }

    branchPred->drainSanityCheck();
}

bool
Fetch::isDrained() const
{
    /* Make sure that threads are either idle of that the commit stage
     * has signaled that draining has completed by setting the drain
     * stall flag. This effectively forces the pipeline to be disabled
     * until the whole system is drained (simulation may continue to
     * drain other components).
     */
    for (ThreadID i = 0; i < numThreads; ++i) {
        // Verify fetch queues are drained
        if (!fetchQueue[i].empty())
            return false;

        // Return false if not idle or drain stalled
        if (fetchStatus[i] != Idle) {
            if (fetchStatus[i] == Blocked && stalls[i].drain)
                continue;
            else
                return false;
        }
    }

    /* The pipeline might start up again in the middle of the drain
     * cycle if the finish translation event is scheduled, so make
     * sure that's not the case.
     */
    return !finishTranslationEvent.scheduled();
}

void
Fetch::takeOverFrom()
{
    assert(cpu->getInstPort().isConnected());
    resetStage();

}

void
Fetch::drainStall(ThreadID tid)
{
    assert(cpu->isDraining());
    assert(!stalls[tid].drain);
    DPRINTF(Drain, "%i: Thread drained.\n", tid);
    stalls[tid].drain = true;
}

void
Fetch::wakeFromQuiesce()
{
    DPRINTF(Fetch, "Waking up from quiesce\n");
    // Hopefully this is safe
    // @todo: Allow other threads to wake from quiesce.
    fetchStatus[0] = Running;
}

void
Fetch::switchToActive()
{
    if (_status == Inactive) {
        DPRINTF(Activity, "Activating stage.\n");

        cpu->activateStage(CPU::FetchIdx);

        _status = Active;
    }
}

void
Fetch::switchToInactive()
{
    if (_status == Active) {
        DPRINTF(Activity, "Deactivating stage.\n");

        cpu->deactivateStage(CPU::FetchIdx);

        _status = Inactive;
    }
}

void
Fetch::deactivateThread(ThreadID tid)
{
    // Update priority list
    auto thread_it = std::find(priorityList.begin(), priorityList.end(), tid);
    if (thread_it != priorityList.end()) {
        priorityList.erase(thread_it);
    }
}

bool
Fetch::lookupAndUpdateNextPC(const DynInstPtr &inst, PCStateBase &next_pc)
{
    // Do branch prediction check here.
    // A bit of a misnomer...next_PC is actually the current PC until
    // this function updates it.
    bool predict_taken;

    if (!inst->isControl()) {
        inst->staticInst->advancePC(next_pc);
        inst->setPredTarg(next_pc);
        inst->setPredTaken(false);
        return false;
    }

    ThreadID tid = inst->threadNumber;
    predict_taken = branchPred->predict(inst->staticInst, inst->seqNum,
                                        next_pc, tid);

    if (predict_taken) {
        DPRINTF(Fetch, "[tid:%i] [sn:%llu] Branch at PC %#x "
                "predicted to be taken to %s\n",
                tid, inst->seqNum, inst->pcState().instAddr(), next_pc);
    } else {
        DPRINTF(Fetch, "[tid:%i] [sn:%llu] Branch at PC %#x "
                "predicted to be not taken\n",
                tid, inst->seqNum, inst->pcState().instAddr());
    }

    DPRINTF(Fetch, "[tid:%i] [sn:%llu] Branch at PC %#x "
            "predicted to go to %s\n",
            tid, inst->seqNum, inst->pcState().instAddr(), next_pc);
    inst->setPredTarg(next_pc);
    inst->setPredTaken(predict_taken);

    // Get and store branch prediction confidence
    double confidence = branchPred->getLastPredictionConfidence(tid);
    inst->setBranchPredConfidence(confidence);

    cpu->fetchStats[tid]->numBranches++;

    if (predict_taken) {
        ++fetchStats.predictedBranches;
    }

    // Dual-path execution: fetch alternate path into APB with proper virtual address translation
    // Uses prefetch-style requests that don't block the main fetch pipeline
    if (apb && cpu->dualPathSwitcher && !cacheBlocked) {
        // Use actual branch predictor confidence
        double confidence = inst->getBranchPredConfidence();

        // Check if we should fetch alternate path based on policy
        if (cpu->dualPathSwitcher->shouldFetchAlternatePath(confidence)) {
            // Calculate alternate path: opposite of predicted path
            std::unique_ptr<PCStateBase> alternate_pc(next_pc.clone());
            Addr alt_vaddr;

            try {
                if (predict_taken) {
                    // Predicted taken, so alternate is fall-through (not taken)
                    inst->staticInst->advancePC(*alternate_pc);
                    alt_vaddr = alternate_pc->instAddr();
                    DPRINTF(Fetch, "[tid:%i] [sn:%llu] Dual-path mode: "
                            "fetching NOT-TAKEN path %#x into APB (confidence=%.2f)\n",
                            tid, inst->seqNum, alt_vaddr, confidence);
                } else {
                    // Predicted not-taken, so alternate is branch target (taken)
                    inst->staticInst->branchTarget(*alternate_pc);
                    alt_vaddr = alternate_pc->instAddr();
                    DPRINTF(Fetch, "[tid:%i] [sn:%llu] Dual-path mode: "
                            "fetching TAKEN path %#x into APB (confidence=%.2f)\n",
                            tid, inst->seqNum, alt_vaddr, confidence);
                }

                // Queue alternate path fetch (non-blocking prefetch style)
                fetchAlternatePath(alt_vaddr, tid, inst->pcState().instAddr());
            } catch (...) {
                // Ignore errors in alternate path calculation
                // This can happen for unconditional branches or other corner cases
            }
        }
    }

    return predict_taken;
}

bool
Fetch::fetchCacheLine(Addr vaddr, ThreadID tid, Addr pc)
{
    Fault fault = NoFault;

    assert(!cpu->switchedOut());

    // @todo: not sure if these should block translation.
    //AlphaDep
    if (cacheBlocked) {
        DPRINTF(Fetch, "[tid:%i] Can't fetch cache line, cache blocked\n",
                tid);
        return false;
    } else if (checkInterrupt(pc) && !delayedCommit[tid]) {
        // Hold off fetch from getting new instructions when:
        // Cache is blocked, or
        // while an interrupt is pending and we're not in PAL mode, or
        // fetch is switched out.
        DPRINTF(Fetch, "[tid:%i] Can't fetch cache line, interrupt pending\n",
                tid);
        return false;
    }

    // Align the fetch address to the start of a fetch buffer segment.
    Addr fetchBufferBlockPC = fetchBufferAlignPC(vaddr);

    DPRINTF(Fetch, "[tid:%i] Fetching cache line %#x for addr %#x\n",
            tid, fetchBufferBlockPC, vaddr);

    // Setup the memReq to do a read of the first instruction's address.
    // Set the appropriate read size and flags as well.
    // Build request here.
    RequestPtr mem_req = std::make_shared<Request>(
        fetchBufferBlockPC, fetchBufferSize,
        Request::INST_FETCH, cpu->instRequestorId(), pc,
        cpu->thread[tid]->contextId());

    mem_req->taskId(cpu->taskId());

    memReq[tid] = mem_req;

    // Initiate translation of the icache block
    fetchStatus[tid] = ItlbWait;
    FetchTranslation *trans = new FetchTranslation(this);
    cpu->mmu->translateTiming(mem_req, cpu->thread[tid]->getTC(),
                              trans, BaseMMU::Execute);
    return true;
}

bool
Fetch::isInIcache(Addr addr, ThreadID tid)
{
    // Check if the given address is currently in the I-cache.
    // We use a heuristic based on recently fetched addresses.
    // 
    // In real hardware, this would be a tag-only cache probe (fast, 1 cycle).
    // For simulation, we approximate by tracking what we've recently fetched.
    
    Addr alignedAddr = fetchBufferAlignPC(addr);
    
    // Check if it's in the current fetch buffer
    if (fetchBufferValid[tid] && fetchBufferPC[tid] == alignedAddr) {
        return true;
    }
    
    // Check our recently fetched tracking set
    if (recentlyFetchedAddrs.find(alignedAddr) != recentlyFetchedAddrs.end()) {
        return true;
    }
    
    // Not found in our approximation - consider it a potential hard case
    return false;
}

void
Fetch::updateRecentlyFetched(Addr addr)
{
    Addr alignedAddr = fetchBufferAlignPC(addr);
    
    // Add to set if not already present
    if (recentlyFetchedAddrs.find(alignedAddr) == recentlyFetchedAddrs.end()) {
        recentlyFetchedAddrs.insert(alignedAddr);
        recentlyFetchedOrder.push_back(alignedAddr);
        
        // Evict oldest if too many (simulates cache capacity)
        while (recentlyFetchedOrder.size() > MAX_RECENT_ICACHE_TRACKING) {
            Addr oldest = recentlyFetchedOrder.front();
            recentlyFetchedOrder.pop_front();
            recentlyFetchedAddrs.erase(oldest);
        }
    }
}

void
Fetch::fetchAlternatePath(Addr altVaddr, ThreadID tid, Addr branchPC)
{
    // Don't fetch if we're switched out
    if (cpu->switchedOut()) {
        return;
    }

    // If cache is blocked, defer this fetch for later
    if (cacheBlocked) {
        if (deferredAltFetches.size() < MAX_DEFERRED_ALT_FETCHES) {
            deferredAltFetches.push_back({altVaddr, tid, branchPC});
            ++fetchStats.altPathFetchDeferred;
            DPRINTF(Fetch, "[tid:%i] Deferring alternate path fetch for %#x "
                    "(cache blocked, queue size: %d)\n",
                    tid, altVaddr, deferredAltFetches.size());
        } else {
            ++fetchStats.altPathFetchDeferredDropped;
            DPRINTF(Fetch, "[tid:%i] Dropping alternate path fetch for %#x "
                    "(deferred queue full)\n", tid, altVaddr);
        }
        return;
    }

    // Align the fetch address to the start of a fetch buffer segment
    Addr fetchBufferBlockPC = fetchBufferAlignPC(altVaddr);

    // Check if we already have an outstanding request for this address
    if (outstandingAltFetches.find(fetchBufferBlockPC) != outstandingAltFetches.end()) {
        DPRINTF(Fetch, "[tid:%i] Alternate path fetch for %#x already outstanding\n",
                tid, fetchBufferBlockPC);
        return;
    }

    // REALISTIC HARDWARE: Limit outstanding alternate path fetches (MSHR-like)
    if (outstandingAltFetches.size() >= MAX_OUTSTANDING_ALT_FETCHES) {
        DPRINTF(Fetch, "[tid:%i] Dropping alternate path fetch for %#x "
                "(outstanding fetch limit %d reached)\n",
                tid, fetchBufferBlockPC, MAX_OUTSTANDING_ALT_FETCHES);
        ++fetchStats.altPathFetchMshrFull;
        return;
    }

    // Check if this address is already in APB
    if (apb && apb->contains(fetchBufferBlockPC)) {
        DPRINTF(Fetch, "[tid:%i] Alternate path %#x already in APB\n",
                tid, fetchBufferBlockPC);
        return;
    }

    // I-CACHE FILTERING: Only insert into APB if NOT already in I-cache
    // This is the key optimization: APB should only store "hard cases"
    // (paths that would cause I-cache misses on recovery)
    // Can be disabled via icacheFilterEnabled parameter
    if (icacheFilterEnabled && isInIcache(fetchBufferBlockPC, tid)) {
        // Path is already in I-cache - this is an "easy case"
        // Don't waste APB entry on it; I-cache can serve it fast
        ++fetchStats.altPathSkippedInIcache;
        
        // Track this address for race condition detection:
        // If path gets evicted before recovery, we'll detect it
        skippedBecauseInIcache.insert(fetchBufferBlockPC);
        
        DPRINTF(Fetch, "[tid:%i] Alternate path %#x already in I-cache, "
                "skipping APB insert (easy case)\n",
                tid, fetchBufferBlockPC);
        return;
    }
    
    // Path is NOT in I-cache - this is a "hard case"
    // APB insertion is valuable here
    ++fetchStats.altPathInsertedHardCase;
    DPRINTF(Fetch, "[tid:%i] Alternate path %#x NOT in I-cache, "
            "proceeding with APB prefetch (hard case)\n",
            tid, fetchBufferBlockPC);

    // Bypass-then-promote policy: check if this address was previously fetched
    // - First fetch: Set NO_CACHE_FILL flag (bypass I-cache insertion)
    // - Subsequent fetch (APB miss): Allow I-cache fill (don't set flag)
    bool firstFetch = (previouslyFetchedAlternates.find(fetchBufferBlockPC) == 
                       previouslyFetchedAlternates.end());
    
    DPRINTF(Fetch, "[tid:%i] Starting alternate path fetch for vaddr %#x (aligned: %#x) "
            "[%s fetch - %s I-cache fill]\n",
            tid, altVaddr, fetchBufferBlockPC,
            firstFetch ? "first" : "repeat",
            firstFetch ? "bypassing" : "allowing");

    // Create a memory request for the alternate path
    // Mark as PREFETCH so it doesn't interfere with normal MSHR state
    Request::FlagsType flags = Request::INST_FETCH | Request::PREFETCH;
    
    // Bypass-then-promote: On first fetch, bypass I-cache fill
    if (firstFetch) {
        flags |= Request::NO_CACHE_FILL;
        // Mark as previously fetched for next time
        previouslyFetchedAlternates.insert(fetchBufferBlockPC);
        ++fetchStats.altPathBypassedIcache;
    } else {
        ++fetchStats.altPathPromotedToIcache;
    }
    
    RequestPtr mem_req = std::make_shared<Request>(
        fetchBufferBlockPC, fetchBufferSize,
        flags, cpu->instRequestorId(), branchPC,
        cpu->thread[tid]->contextId());

    mem_req->taskId(cpu->taskId());

    // Mark this as outstanding and track the translation
    outstandingAltFetches.insert(fetchBufferBlockPC);
    altPathTranslations[fetchBufferBlockPC] = std::make_pair(branchPC, tid);

    // Initiate translation of the alternate path address
    FetchTranslationAlt *trans = new FetchTranslationAlt(this, fetchBufferBlockPC, tid);
    cpu->mmu->translateTiming(mem_req, cpu->thread[tid]->getTC(),
                              trans, BaseMMU::Execute);

    // Track alternate path fetch request
    ++fetchStats.altPathFetchRequests;
}

void
Fetch::finishTranslationAlt(const Fault &fault, const RequestPtr &mem_req,
                             Addr altPC, ThreadID tid)
{
    assert(!cpu->switchedOut());

    // Check if this translation was squashed
    auto it = outstandingAltFetches.find(altPC);
    if (it == outstandingAltFetches.end()) {
        DPRINTF(Fetch, "[tid:%i] Ignoring alternate path translation after squash\n", tid);
        ++fetchStats.altPathFetchSquashed;
        return;
    }

    // If translation was successful, fetch from I-cache
    if (fault == NoFault) {
        // Check that we're not going off into random memory
        if (!cpu->system->isMemAddr(mem_req->getPaddr())) {
            warn("Alternate path address %#x is outside of physical memory\n",
                 mem_req->getPaddr());
            outstandingAltFetches.erase(it);
            altPathTranslations.erase(altPC);
            return;
        }

        // CRITICAL: Check if normal fetch already has an outstanding icache request
        // The same icachePort cannot have multiple simultaneous requests
        // If normal fetch is waiting for icache response, defer the alternate fetch
        if (fetchStatus[tid] == IcacheWaitResponse) {
            DPRINTF(Fetch, "[tid:%i] Normal fetch has outstanding icache request, "
                    "deferring alternate path fetch for %#x\n", tid, altPC);
            
            // Add to deferred queue to retry later
            if (deferredAltFetches.size() < MAX_DEFERRED_ALT_FETCHES) {
                auto trans_it = altPathTranslations.find(altPC);
                if (trans_it != altPathTranslations.end()) {
                    deferredAltFetches.push_back({altPC, tid, trans_it->second.first});
                    ++fetchStats.altPathFetchDeferred;
                }
            } else {
                ++fetchStats.altPathFetchDeferredDropped;
            }
            
            outstandingAltFetches.erase(it);
            altPathTranslations.erase(altPC);
            return;
        }

        // Create packet for alternate path fetch
        PacketPtr data_pkt = new Packet(mem_req, MemCmd::ReadReq);
        data_pkt->dataDynamic(new uint8_t[fetchBufferSize]);

        DPRINTF(Fetch, "[tid:%i] Alternate path translation complete, "
                "fetching from I-cache (paddr: %#x)\n", tid, mem_req->getPaddr());

        // Try to send the request. If port is busy, defer it
        if (!icachePort.sendTimingReq(data_pkt)) {
            DPRINTF(Fetch, "[tid:%i] Alternate path I-cache port busy, "
                    "deferring fetch for %#x\n", tid, altPC);
            
            // Clean up packet
            delete[] data_pkt->getPtr<uint8_t>();
            delete data_pkt;
            
            // Add to deferred queue if there's space
            if (deferredAltFetches.size() < MAX_DEFERRED_ALT_FETCHES) {
                auto trans_it = altPathTranslations.find(altPC);
                if (trans_it != altPathTranslations.end()) {
                    deferredAltFetches.push_back({altPC, tid, trans_it->second.first});
                    ++fetchStats.altPathFetchDeferred;
                }
            } else {
                ++fetchStats.altPathFetchDeferredDropped;
            }
            
            outstandingAltFetches.erase(it);
            altPathTranslations.erase(altPC);
        }
        // Note: packet will be handled in processCacheCompletion via handleIcacheTimingResp
    } else {
        // Translation fault - just drop this alternate path fetch
        DPRINTF(Fetch, "[tid:%i] Alternate path translation fault (%s) for %#x, dropping\n",
                tid, fault->name(), altPC);
        outstandingAltFetches.erase(it);
        altPathTranslations.erase(altPC);
    }
}

void
Fetch::processDeferredAltPathFetches()
{
    // Process deferred alternate path fetches when cache is no longer blocked
    if (cacheBlocked || deferredAltFetches.empty()) {
        return;
    }

    DPRINTF(Fetch, "Processing %d deferred alternate path fetches\n",
            deferredAltFetches.size());

    // Process all deferred fetches (they will check their own constraints)
    while (!deferredAltFetches.empty()) {
        DeferredAltFetch deferred = deferredAltFetches.front();
        deferredAltFetches.pop_front();

        DPRINTF(Fetch, "[tid:%i] Processing deferred alternate path fetch for %#x\n",
                deferred.tid, deferred.altVaddr);

        ++fetchStats.altPathFetchDeferredProcessed;

        // Recursively call fetchAlternatePath - it will handle all checks
        // including if cache becomes blocked again
        fetchAlternatePath(deferred.altVaddr, deferred.tid, deferred.branchPC);

        // If cache became blocked while processing, stop and save remaining for later
        if (cacheBlocked) {
            DPRINTF(Fetch, "Cache blocked again, %d fetches still deferred\n",
                    deferredAltFetches.size());
            break;
        }
    }
}

void
Fetch::finishTranslation(const Fault &fault, const RequestPtr &mem_req)
{
    ThreadID tid = cpu->contextToThread(mem_req->contextId());
    Addr fetchBufferBlockPC = mem_req->getVaddr();

    assert(!cpu->switchedOut());

    // Wake up CPU if it was idle
    cpu->wakeCPU();

    if (fetchStatus[tid] != ItlbWait || mem_req != memReq[tid] ||
        mem_req->getVaddr() != memReq[tid]->getVaddr()) {
        DPRINTF(Fetch, "[tid:%i] Ignoring itlb completed after squash\n",
                tid);
        ++fetchStats.tlbSquashes;
        return;
    }


    // If translation was successful, attempt to read the icache block.
    if (fault == NoFault) {
        // Check that we're not going off into random memory
        // If we have, just wait around for commit to squash something and put
        // us on the right track
        if (!cpu->system->isMemAddr(mem_req->getPaddr())) {
            warn("Address %#x is outside of physical memory, stopping fetch\n",
                    mem_req->getPaddr());
            fetchStatus[tid] = NoGoodAddr;
            memReq[tid] = NULL;
            return;
        }

        // Build packet here.
        PacketPtr data_pkt = new Packet(mem_req, MemCmd::ReadReq);
        data_pkt->dataDynamic(new uint8_t[fetchBufferSize]);

        fetchBufferPC[tid] = fetchBufferBlockPC;
        fetchBufferValid[tid] = false;
        DPRINTF(Fetch, "Fetch: Doing instruction read.\n");

        fetchStats.cacheLines++;

        // Access the cache.
        if (!icachePort.sendTimingReq(data_pkt)) {
            assert(retryPkt == NULL);
            assert(retryTid == InvalidThreadID);
            DPRINTF(Fetch, "[tid:%i] Out of MSHRs!\n", tid);

            fetchStatus[tid] = IcacheWaitRetry;
            retryPkt = data_pkt;
            retryTid = tid;
            cacheBlocked = true;
        } else {
            DPRINTF(Fetch, "[tid:%i] Doing Icache access.\n", tid);
            DPRINTF(Activity, "[tid:%i] Activity: Waiting on I-cache "
                    "response.\n", tid);
            lastIcacheStall[tid] = curTick();
            fetchStatus[tid] = IcacheWaitResponse;

            // Track I-cache accesses during misprediction recovery
            // This happens when we're recovering from a branch misprediction
            // and need to fetch the correct path from I-cache
            if (squashIsBranchMisp[tid] && squashStartTick[tid] > 0) {
                ++fetchStats.icacheAccessesDuringRecovery;
                DPRINTF(Fetch, "[tid:%i] I-cache access during misprediction "
                        "recovery at %#x\n", tid, fetchBufferBlockPC);
            }

            // Notify Fetch Request probe when a packet containing a fetch
            // request is successfully sent
            ppFetchRequestSent->notify(mem_req);
        }
    } else {
        // Don't send an instruction to decode if we can't handle it.
        if (!(numInst < fetchWidth) ||
                !(fetchQueue[tid].size() < fetchQueueSize)) {
            assert(!finishTranslationEvent.scheduled());
            finishTranslationEvent.setFault(fault);
            finishTranslationEvent.setReq(mem_req);
            cpu->schedule(finishTranslationEvent,
                          cpu->clockEdge(Cycles(1)));
            return;
        }
        DPRINTF(Fetch,
                "[tid:%i] Got back req with addr %#x but expected %#x\n",
                tid, mem_req->getVaddr(), memReq[tid]->getVaddr());
        // Translation faulted, icache request won't be sent.
        memReq[tid] = NULL;

        // Send the fault to commit.  This thread will not do anything
        // until commit handles the fault.  The only other way it can
        // wake up is if a squash comes along and changes the PC.
        const PCStateBase &fetch_pc = *pc[tid];

        DPRINTF(Fetch, "[tid:%i] Translation faulted, building noop.\n", tid);
        // We will use a nop in ordier to carry the fault.
        DynInstPtr instruction = buildInst(tid, nopStaticInstPtr, nullptr,
                fetch_pc, fetch_pc, false);
        instruction->setNotAnInst();

        instruction->setPredTarg(fetch_pc);
        instruction->fault = fault;
        wroteToTimeBuffer = true;

        DPRINTF(Activity, "Activity this cycle.\n");
        cpu->activityThisCycle();

        fetchStatus[tid] = TrapPending;

        DPRINTF(Fetch, "[tid:%i] Blocked, need to handle the trap.\n", tid);
        DPRINTF(Fetch, "[tid:%i] fault (%s) detected @ PC %s.\n",
                tid, fault->name(), *pc[tid]);
    }
    _status = updateFetchStatus();
}

void
Fetch::doSquash(const PCStateBase &new_pc, const DynInstPtr squashInst,
        ThreadID tid)
{
    DPRINTF(Fetch, "[tid:%i] Squashing, setting PC to: %s.\n",
            tid, new_pc);

    set(pc[tid], new_pc);
    fetchOffset[tid] = 0;
    if (squashInst && squashInst->pcState().instAddr() == new_pc.instAddr() &&
        !squashInst->isLastMicroop())
        macroop[tid] = squashInst->macroop;
    else
        macroop[tid] = NULL;
    decoder[tid]->reset();

    // Clear the icache miss if it's outstanding.
    if (fetchStatus[tid] == IcacheWaitResponse) {
        DPRINTF(Fetch, "[tid:%i] Squashing outstanding Icache miss.\n",
                tid);
        memReq[tid] = NULL;
    } else if (fetchStatus[tid] == ItlbWait) {
        DPRINTF(Fetch, "[tid:%i] Squashing outstanding ITLB miss.\n",
                tid);
        memReq[tid] = NULL;
    } else if (fetchStatus[tid] == ApbWait) {
        // Cancel pending APB read
        DPRINTF(Fetch, "[tid:%i] Squashing outstanding APB read.\n", tid);
        apbReadyTick[tid] = 0;
        pendingApbAddr[tid] = 0;
    }

    // Get rid of the retrying packet if it was from this thread.
    if (retryTid == tid) {
        assert(cacheBlocked);
        if (retryPkt) {
            delete retryPkt;
        }
        retryPkt = NULL;
        retryTid = InvalidThreadID;
    }

    fetchStatus[tid] = Squashing;

    // Empty fetch queue
    fetchQueue[tid].clear();

    // Clean up any outstanding alternate path fetches for this thread
    for (auto it = outstandingAltFetches.begin(); it != outstandingAltFetches.end();) {
        auto trans_it = altPathTranslations.find(*it);
        if (trans_it != altPathTranslations.end() && trans_it->second.second == tid) {
            // This alternate fetch belongs to the squashed thread
            altPathTranslations.erase(trans_it);
            it = outstandingAltFetches.erase(it);
        } else {
            ++it;
        }
    }

    // Limit size of skippedBecauseInIcache to prevent unbounded growth
    // Keep only the most recent entries (rough LRU by clearing half when too large)
    const size_t MAX_SKIPPED_TRACKING = 256;
    if (skippedBecauseInIcache.size() > MAX_SKIPPED_TRACKING) {
        // Clear oldest half - this is approximate but sufficient for tracking
        size_t toRemove = skippedBecauseInIcache.size() / 2;
        auto it = skippedBecauseInIcache.begin();
        while (toRemove > 0 && it != skippedBecauseInIcache.end()) {
            it = skippedBecauseInIcache.erase(it);
            --toRemove;
        }
    }

    // microops are being squashed, it is not known wheather the
    // youngest non-squashed microop was  marked delayed commit
    // or not. Setting the flag to true ensures that the
    // interrupts are not handled when they cannot be, though
    // some opportunities to handle interrupts may be missed.
    delayedCommit[tid] = true;

    ++fetchStats.squashCycles;
}

void
Fetch::squashFromDecode(const PCStateBase &new_pc, const DynInstPtr squashInst,
        const InstSeqNum seq_num, ThreadID tid)
{
    DPRINTF(Fetch, "[tid:%i] Squashing from decode.\n", tid);

    doSquash(new_pc, squashInst, tid);

    // Tell the CPU to remove any instructions that are in flight between
    // fetch and decode.
    cpu->removeInstsUntil(seq_num, tid);
}

bool
Fetch::checkStall(ThreadID tid) const
{
    bool ret_val = false;

    if (stalls[tid].drain) {
        assert(cpu->isDraining());
        DPRINTF(Fetch,"[tid:%i] Drain stall detected.\n",tid);
        ret_val = true;
    }

    return ret_val;
}

Fetch::FetchStatus
Fetch::updateFetchStatus()
{
    //Check Running
    for (ThreadID tid : *activeThreads) {
        if (fetchStatus[tid] == Running ||
            fetchStatus[tid] == Squashing ||
            fetchStatus[tid] == IcacheAccessComplete ||
            fetchStatus[tid] == ApbWait) {

            if (_status == Inactive) {
                DPRINTF(Activity, "[tid:%i] Activating stage.\n",tid);

                if (fetchStatus[tid] == IcacheAccessComplete) {
                    DPRINTF(Activity, "[tid:%i] Activating fetch due to cache"
                            "completion\n",tid);
                }

                cpu->activateStage(CPU::FetchIdx);
            }

            return Active;
        }
    }

    // Stage is switching from active to inactive, notify CPU of it.
    if (_status == Active) {
        DPRINTF(Activity, "Deactivating stage.\n");

        cpu->deactivateStage(CPU::FetchIdx);
    }

    return Inactive;
}

void
Fetch::squash(const PCStateBase &new_pc, const InstSeqNum seq_num,
        DynInstPtr squashInst, ThreadID tid)
{
    DPRINTF(Fetch, "[tid:%i] Squash from commit.\n", tid);

    // Track squash timing for recovery latency measurement
    squashStartTick[tid] = curTick();
    squashIsBranchMisp[tid] = (squashInst && squashInst->isControl() &&
                               squashInst->mispredicted());

    doSquash(new_pc, squashInst, tid);

    // Tell the CPU to remove any instructions that are not in the ROB.
    cpu->removeInstsNotInROB(tid);
}

void
Fetch::tick()
{
    bool status_change = false;

    wroteToTimeBuffer = false;

    for (ThreadID i = 0; i < numThreads; ++i) {
        issuePipelinedIfetch[i] = false;
    }

    for (ThreadID tid : *activeThreads) {
        // Check the signals for each thread to determine the proper status
        // for each thread.
        bool updated_status = checkSignalsAndUpdate(tid);
        status_change =  status_change || updated_status;
    }

    DPRINTF(Fetch, "Running stage.\n");

    if (FullSystem) {
        if (fromCommit->commitInfo[0].interruptPending) {
            interruptPending = true;
        }

        if (fromCommit->commitInfo[0].clearInterrupt) {
            interruptPending = false;
        }
    }

    for (threadFetched = 0; threadFetched < numFetchingThreads;
         threadFetched++) {
        // Fetch each of the actively fetching threads.
        fetch(status_change);
    }

    // Record number of instructions fetched this cycle for distribution.
    fetchStats.nisnDist.sample(numInst);

    if (status_change) {
        // Change the fetch stage status if there was a status change.
        _status = updateFetchStatus();
    }

    // Issue the next I-cache request if possible.
    for (ThreadID i = 0; i < numThreads; ++i) {
        if (issuePipelinedIfetch[i]) {
            pipelineIcacheAccesses(i);
        }
    }

    // Send instructions enqueued into the fetch queue to decode.
    // Limit rate by fetchWidth.  Stall if decode is stalled.
    unsigned insts_to_decode = 0;
    unsigned available_insts = 0;

    for (auto tid : *activeThreads) {
        if (!stalls[tid].decode) {
            available_insts += fetchQueue[tid].size();
        }
    }

    // Pick a random thread to start trying to grab instructions from
    auto tid_itr = activeThreads->begin();
    std::advance(tid_itr,
            rng->random<uint8_t>(0, activeThreads->size() - 1));

    while (available_insts != 0 && insts_to_decode < decodeWidth) {
        ThreadID tid = *tid_itr;
        if (!stalls[tid].decode && !fetchQueue[tid].empty()) {
            const auto& inst = fetchQueue[tid].front();
            toDecode->insts[toDecode->size++] = inst;
            DPRINTF(Fetch, "[tid:%i] [sn:%llu] Sending instruction to decode "
                    "from fetch queue. Fetch queue size: %i.\n",
                    tid, inst->seqNum, fetchQueue[tid].size());

            wroteToTimeBuffer = true;
            fetchQueue[tid].pop_front();
            insts_to_decode++;
            available_insts--;
        }

        tid_itr++;
        // Wrap around if at end of active threads list
        if (tid_itr == activeThreads->end())
            tid_itr = activeThreads->begin();
    }

    // If there was activity this cycle, inform the CPU of it.
    if (wroteToTimeBuffer) {
        DPRINTF(Activity, "Activity this cycle.\n");
        cpu->activityThisCycle();
    }

    // Process any deferred alternate path fetches
    processDeferredAltPathFetches();

    // Reset the number of the instruction we've fetched.
    numInst = 0;
}

bool
Fetch::checkSignalsAndUpdate(ThreadID tid)
{
    // Update the per thread stall statuses.
    if (fromDecode->decodeBlock[tid]) {
        stalls[tid].decode = true;
    }

    if (fromDecode->decodeUnblock[tid]) {
        assert(stalls[tid].decode);
        assert(!fromDecode->decodeBlock[tid]);
        stalls[tid].decode = false;
    }

    // Check squash signals from commit.
    if (fromCommit->commitInfo[tid].squash) {

        DPRINTF(Fetch, "[tid:%i] Squashing instructions due to squash "
                "from commit.\n",tid);
        // In any case, squash.
        squash(*fromCommit->commitInfo[tid].pc,
               fromCommit->commitInfo[tid].doneSeqNum,
               fromCommit->commitInfo[tid].squashInst, tid);

        // If it was a branch mispredict on a control instruction, update the
        // branch predictor with that instruction, otherwise just kill the
        // invalid state we generated in after sequence number
        if (fromCommit->commitInfo[tid].mispredictInst &&
            fromCommit->commitInfo[tid].mispredictInst->isControl()) {
            branchPred->squash(fromCommit->commitInfo[tid].doneSeqNum,
                    *fromCommit->commitInfo[tid].pc,
                    fromCommit->commitInfo[tid].branchTaken, tid);
        } else {
            branchPred->squash(fromCommit->commitInfo[tid].doneSeqNum,
                              tid);
        }

        return true;
    } else if (fromCommit->commitInfo[tid].doneSeqNum) {
        // Update the branch predictor if it wasn't a squashed instruction
        // that was broadcasted.
        branchPred->update(fromCommit->commitInfo[tid].doneSeqNum, tid);
    }

    // Check squash signals from decode.
    if (fromDecode->decodeInfo[tid].squash) {
        DPRINTF(Fetch, "[tid:%i] Squashing instructions due to squash "
                "from decode.\n",tid);

        // Update the branch predictor.
        if (fromDecode->decodeInfo[tid].branchMispredict) {
            branchPred->squash(fromDecode->decodeInfo[tid].doneSeqNum,
                    *fromDecode->decodeInfo[tid].nextPC,
                    fromDecode->decodeInfo[tid].branchTaken, tid);
        } else {
            branchPred->squash(fromDecode->decodeInfo[tid].doneSeqNum,
                              tid);
        }

        if (fetchStatus[tid] != Squashing) {

            DPRINTF(Fetch, "Squashing from decode with PC = %s\n",
                *fromDecode->decodeInfo[tid].nextPC);
            // Squash unless we're already squashing
            squashFromDecode(*fromDecode->decodeInfo[tid].nextPC,
                             fromDecode->decodeInfo[tid].squashInst,
                             fromDecode->decodeInfo[tid].doneSeqNum,
                             tid);

            return true;
        }
    }

    if (checkStall(tid) &&
        fetchStatus[tid] != IcacheWaitResponse &&
        fetchStatus[tid] != IcacheWaitRetry &&
        fetchStatus[tid] != ItlbWait &&
        fetchStatus[tid] != ApbWait &&
        fetchStatus[tid] != QuiescePending) {
        DPRINTF(Fetch, "[tid:%i] Setting to blocked\n",tid);

        fetchStatus[tid] = Blocked;

        return true;
    }

    if (fetchStatus[tid] == Blocked ||
        fetchStatus[tid] == Squashing) {
        // Switch status to running if fetch isn't being told to block or
        // squash this cycle.
        DPRINTF(Fetch, "[tid:%i] Done squashing, switching to running.\n",
                tid);

        fetchStatus[tid] = Running;

        return true;
    }

    // If we've reached this point, we have not gotten any signals that
    // cause fetch to change its status.  Fetch remains the same as before.
    return false;
}

DynInstPtr
Fetch::buildInst(ThreadID tid, StaticInstPtr staticInst,
        StaticInstPtr curMacroop, const PCStateBase &this_pc,
        const PCStateBase &next_pc, bool trace)
{
    // Get a sequence number.
    InstSeqNum seq = cpu->getAndIncrementInstSeq();

    DynInst::Arrays arrays;
    arrays.numSrcs = staticInst->numSrcRegs();
    arrays.numDests = staticInst->numDestRegs();

    // Create a new DynInst from the instruction fetched.
    DynInstPtr instruction = new (arrays) DynInst(
            arrays, staticInst, curMacroop, this_pc, next_pc, seq, cpu);
    instruction->setTid(tid);

    instruction->setThreadState(cpu->thread[tid]);

    // Dual-path execution: By default, all instructions are on primary path (pathID=0)
    // Alternate path instructions will have this overridden in fetchAlternatePathFromAPB()
    instruction->setPathID(0);
    instruction->setSpeculativePath(false, 0);
    
    // Track primary path instruction fetch
    cpu->cpuStats.dualPathPrimaryInsts++;

    DPRINTF(Fetch, "[tid:%i] Instruction PC %s created [sn:%lli].\n",
            tid, this_pc, seq);

    DPRINTF(Fetch, "[tid:%i] Instruction is: %s\n", tid,
            instruction->staticInst->disassemble(this_pc.instAddr()));

#if TRACING_ON
    if (trace) {
        instruction->traceData =
            cpu->getTracer()->getInstRecord(curTick(), cpu->tcBase(tid),
                    instruction->staticInst, this_pc, curMacroop);
    }
#else
    instruction->traceData = NULL;
#endif

    // Add instruction to the CPU's list of instructions.
    instruction->setInstListIt(cpu->addInst(instruction));

    // Write the instruction to the first slot in the queue
    // that heads to decode.
    assert(numInst < fetchWidth);
    fetchQueue[tid].push_back(instruction);
    assert(fetchQueue[tid].size() <= fetchQueueSize);
    DPRINTF(Fetch, "[tid:%i] Fetch queue entry created (%i/%i).\n",
            tid, fetchQueue[tid].size(), fetchQueueSize);
    //toDecode->insts[toDecode->size++] = instruction;

    // Keep track of if we can take an interrupt at this boundary
    delayedCommit[tid] = instruction->isDelayedCommit();

    return instruction;
}

unsigned
Fetch::fetchAlternatePathFromAPB(ThreadID tid, InstSeqNum branch_seq_num)
{
    /** This function implements the core dual-path fetch logic.
     * 
     * WHEN IT'S CALLED:
     * After the primary path has been fetched in the main fetch() loop,
     * if we have a conditional branch with low confidence.
     *
     * WHAT IT DOES:
     * 1. Looks up the SpeculativePath entry for this branch
     * 2. Checks if we should fetch alternate path (throttling, APB availability)
     * 3. Reads alternate path instructions from APB
     * 4. Creates DynInst objects for each instruction
     * 5. Tags them with pathID=1 and speculative flags
     * 6. Adds them to the fetch queue (alongside primary path insts)
     * 7. Updates the instruction counter for throttling
     *
     * WHY THIS DESIGN:
     * - APB is already populated by existing code (pre-fetch alternate paths)
     * - We just need to READ from APB and tag instructions differently
     * - Simple, leverages existing infrastructure
     * - Graceful: if APB empty or throttled, just returns 0 (no alternate fetch)
     */
    
    // Safety check: Do we even have dual-path infrastructure?
    if (!cpu->dualPathSwitcher || !apb) {
        return 0;  // No dual-path support configured
    }
    
    // Check if dual-path mode is currently active
    if (!cpu->dualPathSwitcher->useDualPath()) {
        return 0;  // In single-path mode, don't fetch alternate
    }
    
    // Look up the speculative path entry for this branch
    auto pathIt = cpu->activeSpeculativePaths.find(branch_seq_num);
    if (pathIt == cpu->activeSpeculativePaths.end()) {
        return 0;  // No active speculative path for this branch
    }
    
    CPU::SpeculativePath &path = pathIt->second;
    
    // Check throttling: has alternate path fetched too many instructions?
    if (path.shouldThrottleFetch()) {
        DPRINTF(Fetch, "[tid:%i] Alternate path throttled (fetched %d/%d insts)\n",
                tid, path.instructionsFetched, path.maxInstructionsAhead);
        
        // Track throttling events
        cpu->cpuStats.dualPathThrottled++;
        
        return 0;  // Throttled, don't fetch more
    }
    
    // Check if APB has the alternate path
    Addr alt_pc = path.alternatePath;
    if (!apb->contains(alt_pc)) {
        DPRINTF(Fetch, "[tid:%i] APB does not contain alternate path %#x\n",
                tid, alt_pc);
        return 0;  // APB miss, can't fetch alternate path
    }
    
    // Great! We can fetch from APB. Read the cache line.
    const uint8_t* apb_line = apb->readLine(alt_pc);
    if (!apb_line) {
        warn("APB contains() returned true but readLine() returned null for %#x\n",
             alt_pc);
        return 0;  // Shouldn't happen, but be defensive
    }
    
    DPRINTF(Fetch, "[tid:%i] Fetching alternate path from APB: PC=%#x, branch_sn=%llu\n",
            tid, alt_pc, branch_seq_num);
    
    // Now we need to decode instructions from the APB line
    // This is similar to the main fetch loop, but simpler (no branches/macroop handling)
    
    unsigned num_alt_insts = 0;
    
    // Create a temporary PC state for the alternate path
    std::unique_ptr<PCStateBase> alt_pc_state(pc[tid]->clone());
    alt_pc_state->set(alt_pc);
    
    // We'll fetch up to fetchWidth instructions OR until we hit a branch
    // (to avoid complexity of handling branches in alternate path)
    // CRITICAL: Must check against numInst to avoid exceeding fetchWidth in buildInst()
    unsigned remaining_bandwidth = (numInst < fetchWidth) ? (fetchWidth - numInst) : 0;
    unsigned fetch_limit = std::min({remaining_bandwidth,
                                     fetchQueueSize - (unsigned)fetchQueue[tid].size(),
                                     4u});  // Cap at 4 for now
    
    // If no bandwidth left, don't fetch alternate path this cycle
    if (fetch_limit == 0) {
        DPRINTF(Fetch, "[tid:%i] No fetch bandwidth for alternate path (numInst=%d)\n",
                tid, numInst);
        return 0;
    }
    
    // Temporary decoder for alternate path
    // Note: In a real implementation, you might reuse decoder[tid] or have a separate one
    // For simplicity, we'll create instructions directly from the APB line
    
    // SIMPLIFIED VERSION: Just create a few instructions from the alternate path
    // In a full implementation, you'd decode the entire cache line properly
    // For now, we'll create up to 4 instructions as a proof of concept
    
    for (unsigned i = 0; i < fetch_limit; ++i) {
        // In a real implementation, you'd decode actual instructions from apb_line
        // For this implementation, we'll create NOP instructions as placeholders
        // This demonstrates the path tagging mechanism
        
        std::unique_ptr<PCStateBase> next_alt_pc(alt_pc_state->clone());
        next_alt_pc->advance();  // Move to next instruction
        
        // Create the instruction (using NOP as placeholder for demonstration)
        // In real implementation: decode from apb_line[offset]
        DynInstPtr alt_inst = buildInst(tid, nopStaticInstPtr, nullptr,
                                       *alt_pc_state, *next_alt_pc, false);
        
        // KEY STEP: Tag this instruction as being from the alternate path
        alt_inst->setPathID(1);  // Path 1 = alternate/speculative path
        alt_inst->setSpeculativePath(true, branch_seq_num);
        
        // Track alternate path instruction fetch
        cpu->cpuStats.dualPathAlternateInsts++;
        
        DPRINTF(Fetch, "[tid:%i] Created alternate path inst [sn:%llu] PC=%#x pathID=1\n",
                tid, alt_inst->seqNum, alt_pc_state->instAddr());
        
        // Move to next instruction
        alt_pc_state = std::move(next_alt_pc);
        num_alt_insts++;
        
        // Note: buildInst() already added instruction to fetchQueue[tid]
        // so we don't need to do it again
    }
    
    // Update the instruction counter for throttling
    path.instructionsFetched += num_alt_insts;
    
    DPRINTF(Fetch, "[tid:%i] Fetched %d alternate path instructions (total: %d/%d)\n",
            tid, num_alt_insts, path.instructionsFetched, path.maxInstructionsAhead);
    
    return num_alt_insts;
}

bool
Fetch::fetchCacheLineNonBlocking(Addr linePC, uint8_t *dst, int size, ThreadID tid)
{
    // Align the requested address the same way the fetch buffer does.
    Addr alignedPC = fetchBufferAlignPC(linePC);

    // FAST PATH: if some thread's fetch buffer already contains this aligned line,
    // copy it immediately. We check this thread's buffer first (tid passed in).
    if (tid != InvalidThreadID) {
        if (fetchBufferValid[tid] && fetchBufferPC[tid] == alignedPC) {
            // fetchBuffer[tid] contains the aligned block
            std::memcpy(dst, fetchBuffer[tid], size);
            if (debugAltFetch) {
                DPRINTF(Fetch, "AltFetch fast-path hit for %#x (tid=%d)\n", alignedPC, tid);
            }
            return true;
        }
    }

    // If a speculative request for this aligned line is already in flight, return false.
    if (outstandingAltFetches.find(alignedPC) != outstandingAltFetches.end()) {
        if (debugAltFetch) {
            DPRINTF(Fetch, "AltFetch already outstanding for %#x\n", alignedPC);
        }
        return false;
    }

    // Build a Request for instruction fetch of the full line.
    RequestPtr req = std::make_shared<Request>(
        alignedPC,                          // physical/virtual? Use existing code path
        size,
        Request::INST_FETCH,
        cpu->instRequestorId());

    // Build packet and allocate a dynamic buffer to hold the returned data.
    PacketPtr pkt = new Packet(req, MemCmd::ReadReq);
    pkt->dataDynamic(new uint8_t[size]);

    // Try to send the timing request to the I-cache port. If the icache port refuses,
    // free the packet and return false (try again later).
    bool sent = icachePort.sendTimingReq(pkt);
    if (!sent) {
        // Port not ready. Free buffers and packet.
        delete[] pkt->getPtr<uint8_t>();
        delete pkt;
        if (debugAltFetch) {
            DPRINTF(Fetch, "AltFetch sendTimingReq rejected for %#x\n", alignedPC);
        }
        return false;
    }

    // Record that this alignedPC is outstanding. We do NOT store the PacketPtr here;
    // we rely on the response path to give us the packet back and match by address.
    outstandingAltFetches.insert(alignedPC);

    if (debugAltFetch) {
        DPRINTF(Fetch, "AltFetch request sent for %#x\n", alignedPC);
    }

    return false; // request issued, data will arrive asynchronously
}

void
Fetch::handleIcacheTimingResp(PacketPtr pkt)
{
    DPRINTF(O3CPU, "Fetch unit received timing\n");

    // Original gem5 assertion
    assert(pkt->req->isUncacheable() ||
           !(pkt->cacheResponding() && !pkt->hasSharers()));

    // Process all cache completions through the normal path
    // This properly handles MSHR cleanup for both normal and alternate path fetches
    processCacheCompletion(pkt);
}


void
Fetch::fetch(bool &status_change)
{
    //////////////////////////////////////////
    // Start actual fetch
    //////////////////////////////////////////
    ThreadID tid = getFetchingThread();

    assert(!cpu->switchedOut());

    if (tid == InvalidThreadID) {
        // Breaks looping condition in tick()
        threadFetched = numFetchingThreads;

        if (numThreads == 1) {  // @todo Per-thread stats
            profileStall(0);
        }

        return;
    }

    DPRINTF(Fetch, "Attempting to fetch from [tid:%i]\n", tid);

    // The current PC.
    PCStateBase &this_pc = *pc[tid];

    Addr pcOffset = fetchOffset[tid];
    Addr fetchAddr = (this_pc.instAddr() + pcOffset) & decoder[tid]->pcMask();

    bool inRom = isRomMicroPC(this_pc.microPC());

    // If returning from the delay of a cache miss, then update the status
    // to running, otherwise do the cache access.  Possibly move this up
    // to tick() function.
    if (fetchStatus[tid] == IcacheAccessComplete) {
        DPRINTF(Fetch, "[tid:%i] Icache miss is complete.\n", tid);

        fetchStatus[tid] = Running;
        status_change = true;
    } else if (fetchStatus[tid] == ApbWait) {
        // Waiting for APB read to complete
        if (curTick() >= apbReadyTick[tid]) {
            // APB read is complete
            Addr apbAddr = pendingApbAddr[tid];
            const uint8_t* line = apb->readLine(apbAddr);
            if (line) {
                std::memcpy(fetchBuffer[tid], line, fetchBufferSize);
                fetchBufferPC[tid] = fetchBufferAlignPC(apbAddr);
                fetchBufferValid[tid] = true;
                fetchStatus[tid] = Running;
                status_change = true;

                // Track APB-assisted recovery
                if (squashIsBranchMisp[tid] && squashStartTick[tid] > 0) {
                    // Measure recovery time: includes APB read latency
                    Tick recoveryTime = curTick() - squashStartTick[tid];
                    ++fetchStats.apbRecoveryHits;
                    fetchStats.apbHitRecoveryLatency.sample(recoveryTime);
                    fetchStats.recoveryLatency.sample(recoveryTime);
                    fetchStats.branchMispredRecoveryCycles += recoveryTime;
                    DPRINTF(Fetch, "[tid:%i] APB hit for recovery! Latency: %d ticks (%d cycles)\n",
                            tid, recoveryTime, recoveryTime / 500);
                    squashStartTick[tid] = 0;
                    squashIsBranchMisp[tid] = false;
                }
            } else {
                // APB miss after wait (shouldn't happen, but fall back to I-cache)
                DPRINTF(Fetch, "[tid:%i] APB read returned null, falling back to I-cache\n", tid);
                fetchStatus[tid] = Running;
            }
        } else {
            // Still waiting for APB read
            ++fetchStats.miscStallCycles;
            return;
        }
    } else if (fetchStatus[tid] == Running) {
        // Align the fetch PC so its at the start of a fetch buffer segment.
        Addr fetchBufferBlockPC = fetchBufferAlignPC(fetchAddr);
        
        // If buffer is no longer valid or fetchAddr has moved to point
        // to the next cache block, AND we have no remaining ucode
        // from a macro-op, then need to fetch from APB or icache.
        if (!(fetchBufferValid[tid] &&
                    fetchBufferBlockPC == fetchBufferPC[tid]) && !inRom &&
                !macroop[tid]) {
            // --- Check APB first (with realistic latency) ---
            if (apb && apb->contains(fetchAddr)) {
                // APB hit: start the read with realistic latency
                pendingApbAddr[tid] = fetchAddr;
                // Model APB read latency: tag lookup + data read
                Tick clockPeriod = cpu->clockPeriod();
                apbReadyTick[tid] = curTick() + (APB_READ_LATENCY_CYCLES * clockPeriod);
                fetchStatus[tid] = ApbWait;
                DPRINTF(Fetch, "[tid:%i] APB hit for 0x%x, waiting %d cycles for data\n",
                        tid, fetchAddr, APB_READ_LATENCY_CYCLES);
                ++fetchStats.miscStallCycles;
                return;
            }
            // APB miss or no APB - fall through to I-cache
            DPRINTF(Fetch, "[tid:%i] Attempting to translate and read "
                    "instruction, starting at PC %s.\n", tid, this_pc);

            fetchCacheLine(fetchAddr, tid, this_pc.instAddr());

            if (fetchStatus[tid] == IcacheWaitResponse) {
                cpu->fetchStats[tid]->icacheStallCycles++;
            }
            else if (fetchStatus[tid] == ItlbWait)
                ++fetchStats.tlbCycles;
            else
                ++fetchStats.miscStallCycles;
            return;
        } else if (checkInterrupt(this_pc.instAddr()) &&
                !delayedCommit[tid]) {
            // Stall CPU if an interrupt is posted and we're not issuing
            // an delayed commit micro-op currently (delayed commit
            // instructions are not interruptable by interrupts, only faults)
            ++fetchStats.miscStallCycles;
            DPRINTF(Fetch, "[tid:%i] Fetch is stalled!\n", tid);
            return;
        }
    } else {
        if (fetchStatus[tid] == Idle) {
            ++fetchStats.idleCycles;
            DPRINTF(Fetch, "[tid:%i] Fetch is idle!\n", tid);
        }

        // Status is Idle, so fetch should do nothing.
        return;
    }

    ++fetchStats.cycles;

    std::unique_ptr<PCStateBase> next_pc(this_pc.clone());

    StaticInstPtr staticInst = NULL;
    StaticInstPtr curMacroop = macroop[tid];

    // If the read of the first instruction was successful, then grab the
    // instructions from the rest of the cache line and put them into the
    // queue heading to decode.

    DPRINTF(Fetch, "[tid:%i] Adding instructions to queue to "
            "decode.\n", tid);

    // Need to keep track of whether or not a predicted branch
    // ended this fetch block.
    bool predictedBranch = false;

    // Need to halt fetch if quiesce instruction detected
    bool quiesce = false;

    const unsigned numInsts = fetchBufferSize / instSize;
    unsigned blkOffset = (fetchAddr - fetchBufferPC[tid]) / instSize;

    auto *dec_ptr = decoder[tid];
    const Addr pc_mask = dec_ptr->pcMask();

    // Loop through instruction memory from the cache.
    // Keep issuing while fetchWidth is available and branch is not
    // predicted taken
    while (numInst < fetchWidth && fetchQueue[tid].size() < fetchQueueSize
           && !predictedBranch && !quiesce) {
        // We need to process more memory if we aren't going to get a
        // StaticInst from the rom, the current macroop, or what's already
        // in the decoder.
        bool needMem = !inRom && !curMacroop && !dec_ptr->instReady();
        fetchAddr = (this_pc.instAddr() + pcOffset) & pc_mask;
        Addr fetchBufferBlockPC = fetchBufferAlignPC(fetchAddr);

        if (needMem) {
            // If buffer is no longer valid or fetchAddr has moved to point
            // to the next cache block then start fetch from icache.
            if (!fetchBufferValid[tid] ||
                fetchBufferBlockPC != fetchBufferPC[tid])
                break;

            if (blkOffset >= numInsts) {
                // We need to process more memory, but we've run out of the
                // current block.
                break;
            }

            memcpy(dec_ptr->moreBytesPtr(),
                    fetchBuffer[tid] + blkOffset * instSize, instSize);
            decoder[tid]->moreBytes(this_pc, fetchAddr);

            if (dec_ptr->needMoreBytes()) {
                blkOffset++;
                fetchAddr += instSize;
                pcOffset += instSize;
            }
        }

        // Extract as many instructions and/or microops as we can from
        // the memory we've processed so far.
        do {
            if (!(curMacroop || inRom)) {
                if (dec_ptr->instReady()) {
                    staticInst = dec_ptr->decode(this_pc);

                    // TODO: Add APB alternate path logic here when integrated with branch predictor
                    // For now, commenting out to fix compilation
                    // if (staticInst->isControl()) {
                    //     // Get predicted target from branch predictor
                    //     // Determine alternate path and speculatively fetch
                    // }

                    // Increment stat of fetched instructions.
                    cpu->fetchStats[tid]->numInsts++;

                    if (staticInst->isMacroop()) {
                        curMacroop = staticInst;
                    } else {
                        pcOffset = 0;
                    }
                } else {
                    // We need more bytes for this instruction so blkOffset and
                    // pcOffset will be updated
                    break;
                }
            }
            // Whether we're moving to a new macroop because we're at the
            // end of the current one, or the branch predictor incorrectly
            // thinks we are...
            bool newMacro = false;
            if (curMacroop || inRom) {
                if (inRom) {
                    staticInst = dec_ptr->fetchRomMicroop(
                            this_pc.microPC(), curMacroop);
                } else {
                    staticInst = curMacroop->fetchMicroop(this_pc.microPC());
                }
                newMacro |= staticInst->isLastMicroop();
            }

            DynInstPtr instruction = buildInst(
                    tid, staticInst, curMacroop, this_pc, *next_pc, true);

            ppFetch->notify(instruction);
            numInst++;

#if TRACING_ON
            if (debug::O3PipeView) {
                instruction->fetchTick = curTick();
            }
#endif

            // DUAL-PATH EXECUTION: Check if this is a conditional branch
            // and we should fetch the alternate path.
            // DISABLED FOR NOW: The dual-path spawning logic conflicts with
            // gem5's memory subsystem (crossbar assertions). This needs careful
            // redesign to properly handle speculative memory requests.
            //
            // TODO: Implement proper dual-path fetching that:
            // 1. Doesn't conflict with existing icache requests
            // 2. Properly handles memory ordering in the crossbar
            // 3. Uses separate fetch queues for alternate paths
            // 4. Coordinates with the memory system for speculative fetches
            /*
            if (instruction->isCondCtrl() && 
                instruction->getPathID() == 0) {  // Only from primary path!
                
                // TODO: Re-enable these checks when DualPathSwitcher/APB are properly initialized
                // For now, always enable dual-path execution for testing
                // cpu->activeSpeculativePaths.empty() &&  // No other alternate paths active!
                // cpu->dualPathSwitcher && apb) {
                
                // Get branch prediction confidence from the instruction
                double confidence = instruction->getBranchPredConfidence();
                
                // Check if we should fetch alternate path for this branch
                // For now, use a simple threshold (confidence < 0.8 = low confidence)
                bool should_fetch_alternate = (confidence < 0.8);
                
                if (should_fetch_alternate) {
                    // Determine the alternate path PC
                    // If branch was predicted taken, alternate is not-taken (fall-through)
                    // If branch was predicted not-taken, alternate is taken (target)
                    Addr alternate_pc;
                    std::unique_ptr<PCStateBase> fallthrough_pc(this_pc.clone());
                    instruction->staticInst->advancePC(*fallthrough_pc);
                    
                    // Check if prediction was taken or not-taken
                    // If predicted target matches fall-through, then predicted not-taken
                    if (instruction->readPredTaken()) {
                        // Predicted taken, alternate is fall-through
                        alternate_pc = fallthrough_pc->instAddr();
                    } else {
                        // Predicted not-taken, alternate is target
                        alternate_pc = instruction->readPredTarg().instAddr();
                    }
                    
                    // Spawn the speculative path (creates entry in CPU's tracking map)
                    // This only creates the metadata; actual fetch happens below
                    bool spawned = cpu->spawnSpeculativePath(instruction, alternate_pc, tid);
                    
                    if (spawned) {
                        DPRINTF(Fetch, "[tid:%i] Spawned dual-path for branch [sn:%llu] "
                               "pred=%#x alt=%#x conf=%.2f\n",
                               tid, instruction->seqNum, instruction->readPredTarg().instAddr(), alternate_pc, confidence);
                        
                        // TODO: Fetch alternate path instructions from APB
                        // For now, just track that we spawned a speculative path
                        // Actually fetching from APB requires proper non-blocking fetch infrastructure
                        // which needs to be implemented carefully to avoid crossbar conflicts
                        
                        // unsigned alt_insts = fetchAlternatePathFromAPB(tid, instruction->seqNum);
                        // if (alt_insts > 0) {
                        //     DPRINTF(Fetch, "[tid:%i] Fetched %d alternate path instructions\n",
                        //            tid, alt_insts);
                        //     numInst += alt_insts;
                        // }
                    }
                }
            }
            */

            set(next_pc, this_pc);

            // If we're branching after this instruction, quit fetching
            // from the same block.
            predictedBranch |= this_pc.branching();
            predictedBranch |= lookupAndUpdateNextPC(instruction, *next_pc);
            if (predictedBranch) {
                DPRINTF(Fetch, "Branch detected with PC = %s\n", this_pc);
            }

            newMacro |= this_pc.instAddr() != next_pc->instAddr();

            // Move to the next instruction, unless we have a branch.
            set(this_pc, *next_pc);
            inRom = isRomMicroPC(this_pc.microPC());

            if (newMacro) {
                fetchAddr = this_pc.instAddr() & pc_mask;
                blkOffset = (fetchAddr - fetchBufferPC[tid]) / instSize;
                pcOffset = 0;
                curMacroop = NULL;
            }

            if (instruction->isQuiesce()) {
                DPRINTF(Fetch,
                        "Quiesce instruction encountered, halting fetch!\n");
                fetchStatus[tid] = QuiescePending;
                status_change = true;
                quiesce = true;
                break;
            }
        } while ((curMacroop || dec_ptr->instReady()) &&
                 numInst < fetchWidth &&
                 fetchQueue[tid].size() < fetchQueueSize);

        // Re-evaluate whether the next instruction to fetch is in micro-op ROM
        // or not.
        inRom = isRomMicroPC(this_pc.microPC());
    }

    if (predictedBranch) {
        DPRINTF(Fetch, "[tid:%i] Done fetching, predicted branch "
                "instruction encountered.\n", tid);
    } else if (numInst >= fetchWidth) {
        DPRINTF(Fetch, "[tid:%i] Done fetching, reached fetch bandwidth "
                "for this cycle.\n", tid);
    } else if (blkOffset >= fetchBufferSize) {
        DPRINTF(Fetch, "[tid:%i] Done fetching, reached the end of the"
                "fetch buffer.\n", tid);
    }

    macroop[tid] = curMacroop;
    fetchOffset[tid] = pcOffset;

    if (numInst > 0) {
        wroteToTimeBuffer = true;
    }

    // pipeline a fetch if we're crossing a fetch buffer boundary and not in
    // a state that would preclude fetching
    fetchAddr = (this_pc.instAddr() + pcOffset) & pc_mask;
    Addr fetchBufferBlockPC = fetchBufferAlignPC(fetchAddr);
    issuePipelinedIfetch[tid] = fetchBufferBlockPC != fetchBufferPC[tid] &&
        fetchStatus[tid] != IcacheWaitResponse &&
        fetchStatus[tid] != ItlbWait &&
        fetchStatus[tid] != IcacheWaitRetry &&
        fetchStatus[tid] != QuiescePending &&
        !curMacroop;
}

void
Fetch::recvReqRetry()
{
    if (retryPkt != NULL) {
        assert(cacheBlocked);
        assert(retryTid != InvalidThreadID);
        assert(fetchStatus[retryTid] == IcacheWaitRetry);

        if (icachePort.sendTimingReq(retryPkt)) {
            fetchStatus[retryTid] = IcacheWaitResponse;
            // Notify Fetch Request probe when a retryPkt is successfully sent.
            // Note that notify must be called before retryPkt is set to NULL.
            ppFetchRequestSent->notify(retryPkt->req);
            retryPkt = NULL;
            retryTid = InvalidThreadID;
            cacheBlocked = false;

            // Process any deferred alternate path fetches now that cache is unblocked
            processDeferredAltPathFetches();
        }
    } else {
        assert(retryTid == InvalidThreadID);
        // Access has been squashed since it was sent out.  Just clear
        // the cache being blocked.
        cacheBlocked = false;

        // Process any deferred alternate path fetches now that cache is unblocked
        processDeferredAltPathFetches();
    }
}

///////////////////////////////////////
//                                   //
//  SMT FETCH POLICY MAINTAINED HERE //
//                                   //
///////////////////////////////////////
ThreadID
Fetch::getFetchingThread()
{
    if (numThreads > 1) {
        switch (fetchPolicy) {
          case SMTFetchPolicy::RoundRobin:
            return roundRobin();
          case SMTFetchPolicy::IQCount:
            return iqCount();
          case SMTFetchPolicy::LSQCount:
            return lsqCount();
          case SMTFetchPolicy::Branch:
            return branchCount();
          default:
            return InvalidThreadID;
        }
    } else {
        auto thread = activeThreads->begin();
        if (thread == activeThreads->end()) {
            return InvalidThreadID;
        }

        ThreadID tid = *thread;

        if (fetchStatus[tid] == Running ||
            fetchStatus[tid] == IcacheAccessComplete ||
            fetchStatus[tid] == ApbWait ||
            fetchStatus[tid] == Idle) {
            return tid;
        } else {
            return InvalidThreadID;
        }
    }
}


ThreadID
Fetch::roundRobin()
{
    auto pri_iter = priorityList.begin();
    auto end      = priorityList.end();

    ThreadID high_pri;

    while (pri_iter != end) {
        high_pri = *pri_iter;

        assert(high_pri <= numThreads);

        if (fetchStatus[high_pri] == Running ||
            fetchStatus[high_pri] == ApbWait ||
            fetchStatus[high_pri] == IcacheAccessComplete ||
            fetchStatus[high_pri] == Idle) {

            priorityList.erase(pri_iter);
            priorityList.push_back(high_pri);

            return high_pri;
        }

        pri_iter++;
    }

    return InvalidThreadID;
}

ThreadID
Fetch::iqCount()
{
    //sorted from lowest->highest
    std::priority_queue<unsigned, std::vector<unsigned>,
                        std::greater<unsigned> > PQ;
    std::map<unsigned, ThreadID> threadMap;

    for (ThreadID tid : *activeThreads) {
        unsigned iqCount = fromIEW->iewInfo[tid].iqCount;

        //we can potentially get tid collisions if two threads
        //have the same iqCount, but this should be rare.
        PQ.push(iqCount);
        threadMap[iqCount] = tid;
    }

    while (!PQ.empty()) {
        ThreadID high_pri = threadMap[PQ.top()];

        if (fetchStatus[high_pri] == Running ||
            fetchStatus[high_pri] == IcacheAccessComplete ||
            fetchStatus[high_pri] == Idle)
            return high_pri;
        else
            PQ.pop();

    }

    return InvalidThreadID;
}

ThreadID
Fetch::lsqCount()
{
    //sorted from lowest->highest
    std::priority_queue<unsigned, std::vector<unsigned>,
                        std::greater<unsigned> > PQ;
    std::map<unsigned, ThreadID> threadMap;

    for (ThreadID tid : *activeThreads) {
        unsigned ldstqCount = fromIEW->iewInfo[tid].ldstqCount;

        //we can potentially get tid collisions if two threads
        //have the same iqCount, but this should be rare.
        PQ.push(ldstqCount);
        threadMap[ldstqCount] = tid;
    }

    while (!PQ.empty()) {
        ThreadID high_pri = threadMap[PQ.top()];

        if (fetchStatus[high_pri] == Running ||
            fetchStatus[high_pri] == IcacheAccessComplete ||
            fetchStatus[high_pri] == Idle)
            return high_pri;
        else
            PQ.pop();
    }

    return InvalidThreadID;
}

ThreadID
Fetch::branchCount()
{
    panic("Branch Count Fetch policy unimplemented\n");
    return InvalidThreadID;
}

void
Fetch::pipelineIcacheAccesses(ThreadID tid)
{
    if (!issuePipelinedIfetch[tid]) {
        return;
    }

    // The next PC to access.
    const PCStateBase &this_pc = *pc[tid];

    if (isRomMicroPC(this_pc.microPC())) {
        return;
    }

    Addr pcOffset = fetchOffset[tid];
    Addr fetchAddr = (this_pc.instAddr() + pcOffset) & decoder[tid]->pcMask();

    // Align the fetch PC so its at the start of a fetch buffer segment.
    Addr fetchBufferBlockPC = fetchBufferAlignPC(fetchAddr);

    // Unless buffer already got the block, fetch it from icache.
    if (!(fetchBufferValid[tid] && fetchBufferBlockPC == fetchBufferPC[tid])) {
        DPRINTF(Fetch, "[tid:%i] Issuing a pipelined I-cache access, "
                "starting at PC %s.\n", tid, this_pc);

        fetchCacheLine(fetchAddr, tid, this_pc.instAddr());
    }
}

void
Fetch::profileStall(ThreadID tid)
{
    DPRINTF(Fetch,"There are no more threads available to fetch from.\n");

    // @todo Per-thread stats

    if (stalls[tid].drain) {
        ++fetchStats.pendingDrainCycles;
        DPRINTF(Fetch, "Fetch is waiting for a drain!\n");
    } else if (activeThreads->empty()) {
        ++fetchStats.noActiveThreadStallCycles;
        DPRINTF(Fetch, "Fetch has no active thread!\n");
    } else if (fetchStatus[tid] == Blocked) {
        ++fetchStats.blockedCycles;
        DPRINTF(Fetch, "[tid:%i] Fetch is blocked!\n", tid);
    } else if (fetchStatus[tid] == Squashing) {
        ++fetchStats.squashCycles;
        DPRINTF(Fetch, "[tid:%i] Fetch is squashing!\n", tid);
    } else if (fetchStatus[tid] == IcacheWaitResponse) {
        cpu->fetchStats[tid]->icacheStallCycles++;
        DPRINTF(Fetch, "[tid:%i] Fetch is waiting cache response!\n",
                tid);
    } else if (fetchStatus[tid] == ItlbWait) {
        ++fetchStats.tlbCycles;
        DPRINTF(Fetch, "[tid:%i] Fetch is waiting ITLB walk to "
                "finish!\n", tid);
    } else if (fetchStatus[tid] == TrapPending) {
        ++fetchStats.pendingTrapStallCycles;
        DPRINTF(Fetch, "[tid:%i] Fetch is waiting for a pending trap!\n",
                tid);
    } else if (fetchStatus[tid] == QuiescePending) {
        ++fetchStats.pendingQuiesceStallCycles;
        DPRINTF(Fetch, "[tid:%i] Fetch is waiting for a pending quiesce "
                "instruction!\n", tid);
    } else if (fetchStatus[tid] == IcacheWaitRetry) {
        ++fetchStats.icacheWaitRetryStallCycles;
        DPRINTF(Fetch, "[tid:%i] Fetch is waiting for an I-cache retry!\n",
                tid);
    } else if (fetchStatus[tid] == NoGoodAddr) {
            DPRINTF(Fetch, "[tid:%i] Fetch predicted non-executable address\n",
                    tid);
    } else {
        DPRINTF(Fetch, "[tid:%i] Unexpected fetch stall reason "
            "(Status: %i)\n",
            tid, fetchStatus[tid]);
    }
}

bool
Fetch::IcachePort::recvTimingResp(PacketPtr pkt)
{
    DPRINTF(O3CPU, "Fetch unit received timing\n");

    // Same asserts as before
    assert(pkt->req->isUncacheable() ||
           !(pkt->cacheResponding() && !pkt->hasSharers()));

    // Call your unified handler that processes:
    //  - normal fetch returns
    //  - alternate-path speculative prefetch returns
    fetch->handleIcacheTimingResp(pkt);

    return true;
}

void
Fetch::IcachePort::recvReqRetry()
{
    fetch->recvReqRetry();
}

} // namespace o3
} // namespace gem5
