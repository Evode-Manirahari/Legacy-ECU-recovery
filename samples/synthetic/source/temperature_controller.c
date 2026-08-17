#include <stdint.h>

#define SYNTH_FUNCTION __attribute__((noinline, used)) static

SYNTH_FUNCTION int32_t temperature_fan_on(int32_t temperature, int32_t threshold) {
    return temperature > threshold ? 1 : 0;
}

SYNTH_FUNCTION int32_t sample_probe(int32_t a, int32_t b, int32_t c) {
    (void)c;
    return temperature_fan_on(a, b);
}

#if defined(SAMPLE_BEHAVIOR_LIBRARY)
__attribute__((visibility("default"))) int32_t sample_invoke(int32_t a, int32_t b, int32_t c) {
    return sample_probe(a, b, c);
}
#else
int main(void) {
    if (sample_probe(91, 90, 0) != 1) {
        return 1;
    }
    if (sample_probe(90, 90, 0) != 0) {
        return 2;
    }
    if (sample_probe(-20, 10, 0) != 0) {
        return 3;
    }
    return 0;
}
#endif
