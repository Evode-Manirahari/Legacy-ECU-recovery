#include <stdint.h>

#define SYNTH_FUNCTION __attribute__((noinline, used)) static

static const int32_t INPUT_AXIS[] = {0, 20, 40, 60, 80, 100};
static const int32_t OUTPUT_TABLE[] = {0, 8, 19, 33, 52, 75};

SYNTH_FUNCTION int32_t lookup_1d(int32_t input) {
    if (input <= INPUT_AXIS[0]) {
        return OUTPUT_TABLE[0];
    }
    if (input >= INPUT_AXIS[5]) {
        return OUTPUT_TABLE[5];
    }

    for (int32_t index = 0; index < 5; ++index) {
        int32_t lower_input = INPUT_AXIS[index];
        int32_t upper_input = INPUT_AXIS[index + 1];
        if (input <= upper_input) {
            int32_t lower_output = OUTPUT_TABLE[index];
            int32_t output_range = OUTPUT_TABLE[index + 1] - lower_output;
            return lower_output + ((input - lower_input) * output_range) /
                                      (upper_input - lower_input);
        }
    }
    return OUTPUT_TABLE[5];
}

SYNTH_FUNCTION int32_t sample_probe(int32_t a, int32_t b, int32_t c) {
    (void)b;
    (void)c;
    return lookup_1d(a);
}

#if defined(SAMPLE_BEHAVIOR_LIBRARY)
__attribute__((visibility("default"))) int32_t sample_invoke(int32_t a, int32_t b, int32_t c) {
    return sample_probe(a, b, c);
}
#else
int main(void) {
    if (sample_probe(-1, 0, 0) != 0) {
        return 1;
    }
    if (sample_probe(50, 0, 0) != 26) {
        return 2;
    }
    if (sample_probe(100, 0, 0) != 75) {
        return 3;
    }
    return 0;
}
#endif
