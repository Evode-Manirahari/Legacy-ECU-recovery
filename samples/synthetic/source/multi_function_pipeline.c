#include <stdint.h>

#define SYNTH_FUNCTION __attribute__((noinline, used)) static

SYNTH_FUNCTION int32_t normalize_sensor(int32_t raw_value, int32_t offset) {
    return raw_value - offset;
}

SYNTH_FUNCTION int32_t apply_gain(int32_t value, int32_t gain_percent) {
    return (value * gain_percent) / 100;
}

SYNTH_FUNCTION int32_t clamp_output(int32_t value) {
    if (value < 0) {
        return 0;
    }
    if (value > 1000) {
        return 1000;
    }
    return value;
}

SYNTH_FUNCTION int32_t control_output(int32_t raw_value, int32_t offset, int32_t gain_percent) {
    int32_t normalized = normalize_sensor(raw_value, offset);
    int32_t amplified = apply_gain(normalized, gain_percent);
    return clamp_output(amplified);
}

SYNTH_FUNCTION int32_t sample_probe(int32_t a, int32_t b, int32_t c) {
    return control_output(a, b, c);
}

#if defined(SAMPLE_BEHAVIOR_LIBRARY)
__attribute__((visibility("default"))) int32_t sample_invoke(int32_t a, int32_t b, int32_t c) {
    return sample_probe(a, b, c);
}
#else
int main(void) {
    if (sample_probe(500, 100, 125) != 500) {
        return 1;
    }
    if (sample_probe(50, 100, 200) != 0) {
        return 2;
    }
    if (sample_probe(1000, 0, 200) != 1000) {
        return 3;
    }
    return 0;
}
#endif
