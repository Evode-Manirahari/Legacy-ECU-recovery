#include <stdint.h>

#define SYNTH_FUNCTION __attribute__((noinline, used)) static

static const int32_t CALIBRATION_TABLE[3][4] = {
    {10, 12, 15, 18},
    {14, 18, 22, 26},
    {19, 24, 30, 36},
};

SYNTH_FUNCTION int32_t clamp_index(int32_t value, int32_t maximum) {
    if (value < 0) {
        return 0;
    }
    if (value > maximum) {
        return maximum;
    }
    return value;
}

SYNTH_FUNCTION int32_t lookup_2d(int32_t rpm_index, int32_t load_index) {
    int32_t row = clamp_index(rpm_index, 2);
    int32_t column = clamp_index(load_index, 3);
    return CALIBRATION_TABLE[row][column];
}

SYNTH_FUNCTION int32_t sample_probe(int32_t a, int32_t b, int32_t c) {
    (void)c;
    return lookup_2d(a, b);
}

#if defined(SAMPLE_BEHAVIOR_LIBRARY)
__attribute__((visibility("default"))) int32_t sample_invoke(int32_t a, int32_t b, int32_t c) {
    return sample_probe(a, b, c);
}
#else
int main(void) {
    if (sample_probe(0, 0, 0) != 10) {
        return 1;
    }
    if (sample_probe(1, 2, 0) != 22) {
        return 2;
    }
    if (sample_probe(8, 9, 0) != 36) {
        return 3;
    }
    return 0;
}
#endif
