#include "cpu/o3/apb.hh"
#include <cstring>
#include <cmath>
#include "debug/APB.hh"

using namespace std;
using namespace gem5;

APB::APB(const Params &p)
    : SimObject(p),
      numEntries(p.num_entries),
      lineSize(p.line_size),
      lineBits(log2(p.line_size)),
      indexMask(p.num_entries - 1),
      table(p.num_entries),
      stats(this)
{
}

// Check if a PC exists in the buffer
bool APB::contains(Addr pc) const
{
    int idx = index(pc);
    const Entry &e = table[idx];

    bool hit = e.valid && e.tag == tagFromPc(pc);
    const_cast<APB*>(this)->stats.accesses++;
    if (hit) {
        const_cast<APB*>(this)->stats.hits++;
    } else {
        const_cast<APB*>(this)->stats.misses++;
    }
    DPRINTF(APB, "contains(0x%x): %s (idx=%d, tag=0x%x)\n",
            pc, hit ? "HIT" : "MISS", idx, tagFromPc(pc));
    return hit;
}

// Read a line from APB
const uint8_t* APB::readLine(Addr pc) const
{
    int idx = index(pc);
    const Entry &e = table[idx];

    if (e.valid && e.tag == tagFromPc(pc)) {
        DPRINTF(APB, "readLine(0x%x): HIT, returning data\n", pc);
        return e.data.data();
    }

    DPRINTF(APB, "readLine(0x%x): MISS\n", pc);
    return nullptr;
}

// Insert a line into the buffer
void APB::insertLine(Addr pc, const uint8_t* data, int size)
{
    int idx = index(pc);
    Entry &e = table[idx];

    e.tag = tagFromPc(pc);
    e.valid = true;
    e.data.resize(lineSize);
    memcpy(e.data.data(), data, std::min(size, (int)lineSize));

    stats.inserts++;

    DPRINTF(APB, "insertLine(0x%x): inserted at idx=%d, tag=0x%x\n",
            pc, idx, e.tag);
}

// Invalidate all entries
void APB::invalidateAll()
{
    for (auto &e : table) {
        e.valid = false;
    }
}

// Constructor for APBStats
APB::APBStats::APBStats(APB *apb)
    : statistics::Group(apb),
      ADD_STAT(accesses, statistics::units::Count::get(),
               "Number of APB accesses"),
      ADD_STAT(hits, statistics::units::Count::get(),
               "Number of APB hits"),
      ADD_STAT(misses, statistics::units::Count::get(),
               "Number of APB misses"),
      ADD_STAT(inserts, statistics::units::Count::get(),
               "Number of APB inserts")
{
}
