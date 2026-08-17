#include <stdint.h>

#define SYNTH_FUNCTION __attribute__((noinline, used)) static

SYNTH_FUNCTION int32_t rpm_from_period(
    int32_t ticks_per_second, int32_t pulses_per_revolution, int32_t period_ticks
) {
    if (ticks_per_second <= 0 || pulses_per_revolution <= 0 || period_ticks <= 0) {
        return 0;
    }
    int64_t numerator = (int64_t)ticks_per_second * 60;
    int64_t denominator = (int64_t)pulses_per_revolution * period_ticks;
    return (int32_t)(numerator / denominator);
}

SYNTH_FUNCTION int32_t sample_probe(int32_t a, int32_t b, int32_t c) {
    return rpm_from_period(a, b, c);
}

#if defined(SAMPLE_BEHAVIOR_LIBRARY)
__attribute__((visibility("default"))) int32_t sample_invoke(int32_t a, int32_t b, int32_t c) {
    return sample_probe(a, b, c);
}
#else
int main(void) {
    if (sample_probe(1000000, 2, 5000) != 6000) {
        return 1;
    }
    if (sample_probe(1000000, 2, 10000) != 3000) {
        return 2;
    }
    if (sample_probe(1000000, 0, 10000) != 0) {
        return 3;
    }
    return 0;
}
#endif
