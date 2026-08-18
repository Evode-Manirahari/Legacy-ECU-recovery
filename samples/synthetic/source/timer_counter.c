#include <stdint.h>

#define SYNTH_FUNCTION __attribute__((noinline, used)) static

/* A free-running 16-bit hardware timer. The interesting behaviour is rollover:
 * a naive `now - previous` goes negative once the counter wraps, which is the
 * classic source of bogus elapsed-time readings in embedded control loops. */
#define TIMER_MODULUS 65536

/* A reading older than this is treated as stale rather than reported. The
 * modulus above disappears from the generated code — the compiler proves the
 * wrap is a sixteen-bit truncation and emits a zero-extend with no immediate —
 * so this threshold is the fixture's one recoverable domain constant. */
#define STALE_TICKS 3000

SYNTH_FUNCTION int32_t advance_counter(int32_t counter, int32_t ticks) {
    int32_t total = counter + ticks;
    return ((total % TIMER_MODULUS) + TIMER_MODULUS) % TIMER_MODULUS;
}

SYNTH_FUNCTION int32_t timer_delta(int32_t now, int32_t previous) {
    int32_t delta = now - previous;
    if (delta < 0) {
        delta += TIMER_MODULUS;
    }
    return delta;
}

SYNTH_FUNCTION int32_t elapsed_ticks(int32_t start, int32_t ticks, int32_t overflow_limit) {
    int32_t now = advance_counter(start, ticks);
    int32_t delta = timer_delta(now, start);
    if (delta > STALE_TICKS) {
        return STALE_TICKS;
    }
    if (overflow_limit > 0 && delta > overflow_limit) {
        return overflow_limit;
    }
    return delta;
}

SYNTH_FUNCTION int32_t sample_probe(int32_t a, int32_t b, int32_t c) {
    return elapsed_ticks(a, b, c);
}

#if defined(SAMPLE_BEHAVIOR_LIBRARY)
__attribute__((visibility("default"))) int32_t sample_invoke(int32_t a, int32_t b, int32_t c) {
    return sample_probe(a, b, c);
}
#else
int main(void) {
    if (sample_probe(1000, 500, 0) != 500) {
        return 1;
    }
    if (sample_probe(65000, 1000, 0) != 1000) {
        return 2;
    }
    if (sample_probe(100, 5000, 1000) != 3000) {
        return 3;
    }
    if (sample_probe(0, 2000, 1000) != 1000) {
        return 4;
    }
    if (sample_probe(0, 0, 0) != 0) {
        return 5;
    }
    return 0;
}
#endif
