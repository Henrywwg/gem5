#ifndef __CPU_O3_APB_HH__
#define __CPU_O3_APB_HH__

#include "sim/sim_object.hh"
#include "base/statistics.hh"
#include "base/types.hh"
#include "params/APB.hh"
#include <vector>
#include <cstdint>
#include <cmath>

namespace gem5
{

class APB : public SimObject
{
  public:
    using Params = APBParams;
    APB(const Params &p);

    bool contains(Addr pc) const;
    const uint8_t* readLine(Addr pc) const;
    void insertLine(Addr pc, const uint8_t* data, int size);
    void invalidateAll();

    unsigned getNumEntries() const { return numEntries; }
    unsigned getLineSize() const { return lineSize; }

    struct APBStats : public statistics::Group
    {
        APBStats(APB *apb);
        statistics::Scalar accesses;
        statistics::Scalar hits;
        statistics::Scalar misses;
        statistics::Scalar inserts;
    } stats;

  private:
    struct Entry {
        Addr tag;
        std::vector<uint8_t> data;
        bool valid;
        Entry() : tag(0), valid(false) {}
    };

    unsigned numEntries;
    unsigned lineSize;
    unsigned lineBits;
    unsigned indexMask;

    std::vector<Entry> table;

    inline int index(Addr pc) const { return (pc >> lineBits) & indexMask; }
    inline Addr tagFromPc(Addr pc) const { return pc >> (lineBits + __builtin_ctz(numEntries)); }
};

} // namespace gem5

#endif // __CPU_O3_APB_HH__
