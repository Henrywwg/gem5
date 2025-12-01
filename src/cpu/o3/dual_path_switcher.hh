/*
 * Copyright (c) 2024 The Regents of the University of Wisconsin-Madison
 * All rights reserved.
 */

#ifndef __CPU_O3_DUAL_PATH_SWITCHER_HH__
#define __CPU_O3_DUAL_PATH_SWITCHER_HH__

#include <deque>

#include "base/statistics.hh"
#include "params/DualPathSwitcher.hh"
#include "sim/sim_object.hh"

namespace gem5
{

namespace o3
{

/**
 * Monitors branch predictor accuracy and controls dual-path execution mode.
 * Starts in dual-path mode, switches to single-path when accuracy is high.
 */
class DualPathSwitcher : public SimObject
{
  public:
    DualPathSwitcher(const DualPathSwitcherParams &params);
    ~DualPathSwitcher() = default;

    /**
     * Update accuracy tracking with a branch outcome.
     * @param correct Whether the branch was predicted correctly
     * @param confidence Branch predictor confidence (0.0-1.0)
     */
    void update(bool correct, double confidence = 0.5);

    /**
     * Check if dual-path mode should be active.
     * @return true if should fetch both paths, false if single-path only
     */
    bool useDualPath() const { return dualPathMode; }

    /**
     * Check if alternate path should be fetched for this branch.
     * For "global" policy: returns useDualPath()
     * For "selective" policy: returns useDualPath() && low confidence
     * @param confidence Branch confidence (0.0 = no confidence, 1.0 = full confidence)
     * @return true if alternate path should be fetched
     */
    bool shouldFetchAlternatePath(double confidence) const;

    /**
     * Get the fetch policy mode.
     * @return "global" or "selective"
     */
    const std::string& getFetchPolicy() const { return fetchPolicy; }

    /**
     * Get current prediction accuracy.
     * @return Accuracy as a value between 0.0 and 1.0
     */
    double getCurrentAccuracy() const;

    /**
     * Finalize statistics at end of simulation.
     * Updates cycle counters to current tick.
     */
    void regStats() override;

  protected:
    /** Window size for accuracy tracking */
    const unsigned windowSize;

    /** Threshold to switch from dual-path to single-path */
    const double highThreshold;

    /** Threshold to switch back to dual-path (hysteresis) */
    const double lowThreshold;

    /** Fetch policy: "global" or "selective" */
    const std::string fetchPolicy;

    /** Confidence threshold for selective policy */
    const double confidenceThreshold;

    /** Switching mode: "accuracy" or "confidence" */
    const std::string switchingMode;

    /** Current mode flag */
    bool dualPathMode;

    /** Sliding window of branch outcomes (true = correct, false = incorrect) */
    std::deque<bool> accuracyWindow;

    /** Count of correct predictions in the window */
    unsigned correctCount;

    /** Sliding window of branch confidence values (for confidence-based mode) */
    std::deque<double> confidenceWindow;

    /** Sum of confidence values in the window */
    double confidenceSum;

    /** Most recent confidence value (for immediate switching in confidence mode) */
    double lastConfidence;

    /** Total branches processed since last mode switch */
    unsigned branchesSinceSwitch;

    /** Tick when last mode switch occurred */
    Tick lastSwitchTick;

    /** Total ticks spent in dual-path mode */
    Tick ticksInDualPath;

    /** Total ticks spent in single-path mode */
    Tick ticksInSinglePath;

    /** Tick when switcher was created */
    Tick creationTick;

    /** Current consecutive mispredictions */
    unsigned consecutiveMispredictions;

    /** Maximum consecutive mispredictions seen in single-path mode */
    unsigned maxConsecutiveMispredictionsInSinglePath;

    /** Longest continuous duration in single-path mode (in ticks) */
    Tick longestSinglePathDuration;

    /** Tick when current single-path period started (0 if not in single-path) */
    Tick currentSinglePathStart;

    /** Update the dual-path mode based on current accuracy */
    void updateMode();

    struct DualPathSwitcherStats : public statistics::Group
    {
        DualPathSwitcherStats(DualPathSwitcher *switcher);

        /** Number of times switched to dual-path mode */
        statistics::Scalar switchesToDualPath;

        /** Number of times switched to single-path mode */
        statistics::Scalar switchesToSinglePath;

        /** Current accuracy */
        statistics::Formula currentAccuracy;

        /** Number of branches processed */
        statistics::Scalar totalBranches;

        /** Number of correct predictions */
        statistics::Scalar correctPredictions;

        /** Number of branches processed in dual-path mode */
        statistics::Scalar branchesInDualPath;

        /** Number of branches processed in single-path mode */
        statistics::Scalar branchesInSinglePath;

        /** Tick of first switch to single-path mode (0 if never switched) */
        statistics::Scalar firstSwitchToSinglePathTick;

        /** Tick of last switch to dual-path mode (0 if never switched) */
        statistics::Scalar lastSwitchToDualPathTick;

        /** Tick of last switch to single-path mode (0 if never switched) */
        statistics::Scalar lastSwitchToSinglePathTick;

        /** Total cycles spent in dual-path mode */
        statistics::Scalar cyclesInDualPath;

        /** Total cycles spent in single-path mode */
        statistics::Scalar cyclesInSinglePath;

        /** Percentage of time in dual-path mode */
        statistics::Formula dualPathTimeRatio;

        /** Average branches between switches */
        statistics::Formula avgBranchesBetweenSwitches;

        /** Distribution of accuracy when in dual-path mode */
        statistics::Distribution accuracyInDualPath;

        /** Distribution of accuracy when in single-path mode */
        statistics::Distribution accuracyInSinglePath;

        /** Maximum consecutive mispredictions while in single-path mode */
        statistics::Scalar maxConsecutiveMispredInSinglePath;

        /** Total number of times had 5+ consecutive mispredictions in single-path */
        statistics::Scalar mispredictionSpikesInSinglePath;

        /** Longest continuous duration spent in single-path mode (ticks) */
        statistics::Scalar longestSinglePathPeriod;

        /** Number of transitions: dual->single vs single->dual ratio */
        statistics::Formula switchImbalanceRatio;

        /** Percentage of total branches that occurred after last switch to single-path */
        statistics::Formula branchesAfterFinalSinglePathSwitch;

        /** Minimum confidence value seen */
        statistics::Scalar minConfidence;

        /** Maximum confidence value seen */
        statistics::Scalar maxConfidence;

        /** Average confidence value */
        statistics::Formula avgConfidence;

        /** Sum of all confidence values (for average calculation) */
        statistics::Scalar totalConfidence;

        /** Histogram of confidence values (binned in 0.1 increments) */
        statistics::Distribution confidenceDistribution;
    } stats;
};

} // namespace o3
} // namespace gem5

#endif // __CPU_O3_DUAL_PATH_SWITCHER_HH__
