#include <stdint.h>

#define SYNTH_FUNCTION __attribute__((noinline, used)) static

/* A status word of the kind an ECU keeps in a diagnostic register: a packed
 * nibble field plus a window of independent flag bits. Unsigned arithmetic is
 * used throughout so shifting and masking stay defined for every input. */
#define FIELD_MASK 0x0Fu
#define FLAG_WINDOW 0xFFFFu
#define MAX_FIELD_SHIFT 28
#define FIELD_RESULT_SHIFT 8

SYNTH_FUNCTION int32_t extract_field(int32_t word, int32_t shift) {
    if (shift < 0 || shift > MAX_FIELD_SHIFT) {
        return 0;
    }
    return (int32_t)(((uint32_t)word >> (uint32_t)shift) & FIELD_MASK);
}

SYNTH_FUNCTION int32_t count_active_flags(int32_t word) {
    uint32_t bits = (uint32_t)word & FLAG_WINDOW;
    int32_t total = 0;
    while (bits != 0u) {
        total += (int32_t)(bits & 1u);
        bits >>= 1u;
    }
    return total;
}

SYNTH_FUNCTION int32_t bitmask_status(int32_t word, int32_t shift, int32_t clear_mask) {
    int32_t retained = (int32_t)((uint32_t)word & ~(uint32_t)clear_mask);
    int32_t field = extract_field(retained, shift);
    int32_t flags = count_active_flags(retained);
    return (field << FIELD_RESULT_SHIFT) | flags;
}

SYNTH_FUNCTION int32_t sample_probe(int32_t a, int32_t b, int32_t c) {
    return bitmask_status(a, b, c);
}

#if defined(SAMPLE_BEHAVIOR_LIBRARY)
__attribute__((visibility("default"))) int32_t sample_invoke(int32_t a, int32_t b, int32_t c) {
    return sample_probe(a, b, c);
}
#else
int main(void) {
    if (sample_probe(0x1234, 8, 0) != 517) {
        return 1;
    }
    if (sample_probe(0xFFFF, 4, 0x0F00) != 3852) {
        return 2;
    }
    if (sample_probe(0, 0, 0) != 0) {
        return 3;
    }
    if (sample_probe(0xFF, 64, 0) != 8) {
        return 4;
    }
    return 0;
}
#endif
