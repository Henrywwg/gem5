#include "cpu/o3/APB.hh"
#include <cstring>
#include <cmath>

using namespace std;
using namespace gem5;

APB::APB(const APBParams &p)
    : SimObject(p),
      cpu_side(this, "CPU fetch port"),
      l1i_side(this, "L1I master port"),
      numEntries(p.num_entries),
      lineSize(p.line_size),
      lineBits(log2(p.line_size)),
      indexMask(p.num_entries - 1),
      table(p.num_entries)
{
    // Initialize stats
    stats.accesses = 0;
    stats.hits     = 0;
    stats.misses   = 0;
    stats.inserts  = 0;
}

// Check if a PC exists in the buffer
bool APB::contains(Addr pc) const
{
    stats.accesses++;

    int idx = index(pc);
    const Entry &e = table[idx];

    if (e.valid && e.tag == tagFromPc(pc)) {
        stats.hits++;
        return true;
    }

    stats.misses++;
    return false;
}

// Read a line from APB
const uint8_t* APB::readLine(Addr pc) const
{
    stats.accesses++;

    int idx = index(pc);
    const Entry &e = table[idx];

    if (e.valid && e.tag == tagFromPc(pc)) {
        stats.hits++;
        return e.data.data();
    }

    stats.misses++;
    return nullptr;
}

// Insert a line into the buffer
void APB::insertLine(Addr pc, const uint8_t* data, int size)
{
    int idx = index(pc);
    Entry &e = table[idx];

    e.tag = tagFromPc(pc);
    e.valid = true;
    e.data.resize(lineSize); // ensure correct line size
    memcpy(e.data.data(), data, std::min(size, lineSize));

    stats.inserts++;
}

// Invalidate all entries
void APB::invalidateAll()
{
    for (auto &e : table) {
        e.valid = false;
    }
}

// Constructor for APBStats
APB::APBStats::APBStats(statistics::Group *parent)
    : statistics::Group(parent)
{
    accesses = defineScalar("accesses", "Number of APB accesses");
    hits     = defineScalar("hits", "Number of APB hits");
    misses   = defineScalar("misses", "Number of APB misses");
    inserts  = defineScalar("inserts", "Number of APB inserts");
}
