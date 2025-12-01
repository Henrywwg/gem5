/*
 * Copyright (c) 2024 The Regents of the University of Wisconsin-Madison
 * All rights reserved.
 */

#include "cpu/o3/dual_path_switcher.hh"

#include "base/trace.hh"
#include "debug/DualPathSwitch.hh"
#include "sim/cur_tick.hh"

namespace gem5
{

namespace o3
{

DualPathSwitcher::DualPathSwitcher(const DualPathSwitcherParams &params)
    : SimObject(params),
      windowSize(params.window_size),
      highThreshold(params.high_threshold / 100.0),
      lowThreshold(params.low_threshold / 100.0),
      fetchPolicy(params.fetch_policy),
      confidenceThreshold(params.confidence_threshold / 100.0),
      switchingMode(params.switching_mode),
      dualPathMode(params.initial_dual_path),
      correctCount(0),
      confidenceSum(0.0),
      lastConfidence(0.5),
      branchesSinceSwitch(0),
      lastSwitchTick(curTick()),
      ticksInDualPath(0),
      ticksInSinglePath(0),
      creationTick(curTick()),
      consecutiveMispredictions(0),
      maxConsecutiveMispredictionsInSinglePath(0),
      longestSinglePathDuration(0),
      currentSinglePathStart(0),
      stats(this)
{
    DPRINTF(DualPathSwitch, "DualPathSwitcher created: window=%d, "
            "high_threshold=%.2f%%, low_threshold=%.2f%%, initial_mode=%s, "
            "fetch_policy=%s, confidence_threshold=%.2f%%, switching_mode=%s\n",
            windowSize, highThreshold * 100.0, lowThreshold * 100.0,
            dualPathMode ? "dual-path" : "single-path",
            fetchPolicy.c_str(), confidenceThreshold * 100.0, switchingMode.c_str());
}

void
DualPathSwitcher::update(bool correct, double confidence)
{
    stats.totalBranches++;
    if (correct) {
        stats.correctPredictions++;
        consecutiveMispredictions = 0;  // Reset on correct prediction
    } else {
        consecutiveMispredictions++;

        // Track misprediction spikes in single-path mode
        if (!dualPathMode) {
            if (consecutiveMispredictions > maxConsecutiveMispredictionsInSinglePath) {
                maxConsecutiveMispredictionsInSinglePath = consecutiveMispredictions;
            }

            // Count significant misprediction spikes (5+ consecutive misses)
            if (consecutiveMispredictions == 5) {
                stats.mispredictionSpikesInSinglePath++;
            }
        }
    }

    // Track branches per mode
    if (dualPathMode) {
        stats.branchesInDualPath++;
    } else {
        stats.branchesInSinglePath++;
    }

    branchesSinceSwitch++;

    // Add new outcome to accuracy window
    accuracyWindow.push_back(correct);
    if (correct) {
        correctCount++;
    }

    // Remove oldest outcome if window is full
    if (accuracyWindow.size() > windowSize) {
        bool oldest = accuracyWindow.front();
        accuracyWindow.pop_front();
        if (oldest) {
            correctCount--;
        }
    }

    // Store immediate confidence for instant switching decisions
    lastConfidence = confidence;

    // Track confidence statistics
    stats.totalConfidence += confidence;
    stats.confidenceDistribution.sample(confidence * 100.0);

    // Update min/max confidence
    if (stats.totalBranches.value() == 1) {
        // First branch - initialize min/max
        stats.minConfidence = confidence;
        stats.maxConfidence = confidence;
    } else {
        if (confidence < stats.minConfidence.value()) {
            stats.minConfidence = confidence;
        }
        if (confidence > stats.maxConfidence.value()) {
            stats.maxConfidence = confidence;
        }
    }

    // Also track in window for statistics/analysis
    confidenceWindow.push_back(confidence);
    confidenceSum += confidence;

    // Remove oldest confidence if window is full
    if (confidenceWindow.size() > windowSize) {
        double oldest_conf = confidenceWindow.front();
        confidenceWindow.pop_front();
        confidenceSum -= oldest_conf;
    }

    // Update mode based on accuracy or immediate confidence
    updateMode();

    // Sample accuracy for distribution (after window is established)
    if (accuracyWindow.size() >= windowSize) {
        double accuracy = getCurrentAccuracy();
        if (dualPathMode) {
            stats.accuracyInDualPath.sample(accuracy * 100.0);
        } else {
            stats.accuracyInSinglePath.sample(accuracy * 100.0);
        }
    }
}

double
DualPathSwitcher::getCurrentAccuracy() const
{
    if (accuracyWindow.empty()) {
        return 0.0;
    }
    return static_cast<double>(correctCount) / accuracyWindow.size();
}

void
DualPathSwitcher::regStats()
{
    SimObject::regStats();

    // Update final cycle counts
    Tick currentTick = curTick();
    Tick ticksSinceSwitch = currentTick - lastSwitchTick;

    if (dualPathMode) {
        ticksInDualPath += ticksSinceSwitch;
    } else {
        ticksInSinglePath += ticksSinceSwitch;

        // Check if current single-path period is the longest
        if (currentSinglePathStart > 0) {
            Tick currentDuration = currentTick - currentSinglePathStart;
            if (currentDuration > longestSinglePathDuration) {
                longestSinglePathDuration = currentDuration;
            }
        }
    }

    // Convert ticks to cycles for statistics
    stats.cyclesInDualPath = ticksInDualPath;
    stats.cyclesInSinglePath = ticksInSinglePath;
    stats.maxConsecutiveMispredInSinglePath = maxConsecutiveMispredictionsInSinglePath;
    stats.longestSinglePathPeriod = longestSinglePathDuration;

    DPRINTF(DualPathSwitch, "Final statistics: dual-path cycles=%llu, "
            "single-path cycles=%llu, total switches=%u, "
            "max consecutive misses in single-path=%u, misprediction spikes=%u\n",
            ticksInDualPath, ticksInSinglePath,
            (unsigned)(stats.switchesToDualPath.value() + stats.switchesToSinglePath.value()),
            maxConsecutiveMispredictionsInSinglePath,
            (unsigned)stats.mispredictionSpikesInSinglePath.value());
}

bool
DualPathSwitcher::shouldFetchAlternatePath(double confidence) const
{
    // Selective policy: make per-branch decisions based on confidence, ignore global mode
    if (fetchPolicy == "selective") {
        // Fetch alternate path when confidence is BELOW threshold
        return confidence < confidenceThreshold;
    }

    // Global policy: respect global dual-path mode flag
    if (fetchPolicy == "global") {
        // If not in dual-path mode, never fetch alternate paths
        if (!dualPathMode) {
            return false;
        }
        // In dual-path mode, check confidence threshold
        return confidence < confidenceThreshold;
    }

    // Unknown policy, default to global behavior
    warn_once("Unknown fetch policy '%s', defaulting to global policy\n",
              fetchPolicy.c_str());
    if (!dualPathMode) {
        return false;
    }
    return confidence < confidenceThreshold;
}

void
DualPathSwitcher::updateMode()
{
    double metric;  // The metric used for switching decision
    const char* metricName;
    bool shouldSwitchToSingle, shouldSwitchToDual;

    // Choose metric based on switching mode
    if (switchingMode == "confidence") {
        // Use IMMEDIATE confidence (not windowed average)
        // This allows instant response to low-confidence predictions
        metric = lastConfidence;
        metricName = "confidence";

        // For confidence: HIGH confidence → single-path, LOW confidence → dual-path
        shouldSwitchToSingle = (dualPathMode && metric >= highThreshold);
        shouldSwitchToDual = (!dualPathMode && metric < lowThreshold);
    } else {
        // Use windowed accuracy (smoothed over time)
        // Need full window before making decisions
        if (accuracyWindow.size() < windowSize) {
            return;  // Not enough samples yet
        }
        metric = getCurrentAccuracy();
        metricName = "accuracy";

        // For accuracy: HIGH accuracy → single-path, LOW accuracy → dual-path
        shouldSwitchToSingle = (dualPathMode && metric >= highThreshold);
        shouldSwitchToDual = (!dualPathMode && metric < lowThreshold);
    }

    bool previousMode = dualPathMode;
    Tick currentTick = curTick();
    Tick ticksSinceSwitch = currentTick - lastSwitchTick;

    // Update time counters for previous mode
    if (previousMode) {
        ticksInDualPath += ticksSinceSwitch;
    } else {
        ticksInSinglePath += ticksSinceSwitch;
    }

    // Switch from dual-path to single-path if metric is high
    if (shouldSwitchToSingle) {
        dualPathMode = false;
        stats.switchesToSinglePath++;

        // Start tracking this single-path period
        currentSinglePathStart = currentTick;

        // Record first switch to single-path
        if (stats.firstSwitchToSinglePathTick.value() == 0) {
            stats.firstSwitchToSinglePathTick = currentTick;
        }
        stats.lastSwitchToSinglePathTick = currentTick;

        DPRINTF(DualPathSwitch, "Switched to SINGLE-PATH mode at tick %llu "
                "(%s=%.2f%%, threshold=%.2f%%, branches since last switch=%u, mode=%s)\n",
                currentTick, metricName, metric * 100.0, highThreshold * 100.0,
                branchesSinceSwitch, switchingMode.c_str());

        branchesSinceSwitch = 0;
        lastSwitchTick = currentTick;
    }
    // Switch from single-path to dual-path if metric drops (hysteresis)
    else if (shouldSwitchToDual) {
        // Track duration of single-path period that just ended
        if (currentSinglePathStart > 0) {
            Tick duration = currentTick - currentSinglePathStart;
            if (duration > longestSinglePathDuration) {
                longestSinglePathDuration = duration;
            }
            currentSinglePathStart = 0;
        }

        dualPathMode = true;
        stats.switchesToDualPath++;
        stats.lastSwitchToDualPathTick = currentTick;

        DPRINTF(DualPathSwitch, "Switched to DUAL-PATH mode at tick %llu "
                "(%s=%.2f%%, threshold=%.2f%%, branches since last switch=%u, mode=%s)\n",
                currentTick, metricName, metric * 100.0, lowThreshold * 100.0,
                branchesSinceSwitch, switchingMode.c_str());

        branchesSinceSwitch = 0;
        lastSwitchTick = currentTick;
    }
    // No switch - just update tick counters
    else {
        lastSwitchTick = currentTick;
    }
}

DualPathSwitcher::DualPathSwitcherStats::DualPathSwitcherStats(
    DualPathSwitcher *switcher)
    : statistics::Group(switcher),
      ADD_STAT(switchesToDualPath, statistics::units::Count::get(),
               "Number of times switched to dual-path mode"),
      ADD_STAT(switchesToSinglePath, statistics::units::Count::get(),
               "Number of times switched to single-path mode"),
      ADD_STAT(currentAccuracy, statistics::units::Ratio::get(),
               "Current prediction accuracy"),
      ADD_STAT(totalBranches, statistics::units::Count::get(),
               "Total branches processed"),
      ADD_STAT(correctPredictions, statistics::units::Count::get(),
               "Total correct predictions"),
      ADD_STAT(branchesInDualPath, statistics::units::Count::get(),
               "Branches processed while in dual-path mode"),
      ADD_STAT(branchesInSinglePath, statistics::units::Count::get(),
               "Branches processed while in single-path mode"),
      ADD_STAT(firstSwitchToSinglePathTick, statistics::units::Tick::get(),
               "Tick when first switched to single-path mode (0 if never)"),
      ADD_STAT(lastSwitchToDualPathTick, statistics::units::Tick::get(),
               "Tick of most recent switch to dual-path mode (0 if never)"),
      ADD_STAT(lastSwitchToSinglePathTick, statistics::units::Tick::get(),
               "Tick of most recent switch to single-path mode (0 if never)"),
      ADD_STAT(cyclesInDualPath, statistics::units::Cycle::get(),
               "Total cycles spent in dual-path mode"),
      ADD_STAT(cyclesInSinglePath, statistics::units::Cycle::get(),
               "Total cycles spent in single-path mode"),
      ADD_STAT(dualPathTimeRatio, statistics::units::Ratio::get(),
               "Fraction of time spent in dual-path mode"),
      ADD_STAT(avgBranchesBetweenSwitches, statistics::units::Ratio::get(),
               "Average branches processed between mode switches"),
      ADD_STAT(accuracyInDualPath, statistics::units::Ratio::get(),
               "Distribution of accuracy while in dual-path mode"),
      ADD_STAT(accuracyInSinglePath, statistics::units::Ratio::get(),
               "Distribution of accuracy while in single-path mode"),
      ADD_STAT(maxConsecutiveMispredInSinglePath, statistics::units::Count::get(),
               "Maximum consecutive mispredictions observed in single-path mode"),
      ADD_STAT(mispredictionSpikesInSinglePath, statistics::units::Count::get(),
               "Number of times had 5+ consecutive mispredictions in single-path mode"),
      ADD_STAT(longestSinglePathPeriod, statistics::units::Tick::get(),
               "Longest continuous duration in single-path mode (ticks)"),
      ADD_STAT(switchImbalanceRatio, statistics::units::Ratio::get(),
               "Ratio of switches to single-path vs switches to dual-path"),
      ADD_STAT(branchesAfterFinalSinglePathSwitch, statistics::units::Count::get(),
               "Number of branches executed after final switch to single-path"),
      ADD_STAT(minConfidence, statistics::units::Ratio::get(),
               "Minimum confidence value seen"),
      ADD_STAT(maxConfidence, statistics::units::Ratio::get(),
               "Maximum confidence value seen"),
      ADD_STAT(avgConfidence, statistics::units::Ratio::get(),
               "Average confidence value across all branches"),
      ADD_STAT(totalConfidence, statistics::units::Ratio::get(),
               "Sum of all confidence values (for average calculation)"),
      ADD_STAT(confidenceDistribution, statistics::units::Ratio::get(),
               "Distribution of branch predictor confidence values")
{
    currentAccuracy = correctPredictions / totalBranches;
    dualPathTimeRatio = cyclesInDualPath / (cyclesInDualPath + cyclesInSinglePath);
    avgBranchesBetweenSwitches = totalBranches / (switchesToDualPath + switchesToSinglePath);
    avgConfidence = totalConfidence / totalBranches;

    // Ratio > 1 means more switches away from dual-path than back to it (stuck in single-path)
    switchImbalanceRatio = switchesToSinglePath / switchesToDualPath;

    // If we switched to single-path and never back, this shows how much we missed
    branchesAfterFinalSinglePathSwitch =
        (totalBranches - branchesInDualPath) / totalBranches;

    // Configure distributions for accuracy (0-100%)
    accuracyInDualPath
        .init(/* base */ 0, /* max */ 100, /* bucket size */ 5)
        .flags(statistics::pdf | statistics::cdf);

    accuracyInSinglePath
        .init(/* base */ 0, /* max */ 100, /* bucket size */ 5)
        .flags(statistics::pdf | statistics::cdf);

    // Configure distribution for confidence (0-100%)
    confidenceDistribution
        .init(/* base */ 0, /* max */ 100, /* bucket size */ 5)
        .flags(statistics::pdf | statistics::cdf);
}

} // namespace o3
} // namespace gem5
