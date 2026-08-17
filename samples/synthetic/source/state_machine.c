#include <stdint.h>

#define SYNTH_FUNCTION __attribute__((noinline, used)) static

enum ControllerState {
    STATE_OFF = 0,
    STATE_CRANKING = 1,
    STATE_RUNNING = 2,
    STATE_FAULT = 3,
};

SYNTH_FUNCTION int32_t next_state(int32_t current_state, int32_t rpm, int32_t fault) {
    if (fault != 0 || current_state == STATE_FAULT) {
        return STATE_FAULT;
    }
    switch (current_state) {
        case STATE_OFF:
            return rpm > 0 ? STATE_CRANKING : STATE_OFF;
        case STATE_CRANKING:
            if (rpm == 0) {
                return STATE_OFF;
            }
            return rpm >= 600 ? STATE_RUNNING : STATE_CRANKING;
        case STATE_RUNNING:
            return rpm == 0 ? STATE_OFF : STATE_RUNNING;
        default:
            return STATE_FAULT;
    }
}

SYNTH_FUNCTION int32_t sample_probe(int32_t a, int32_t b, int32_t c) {
    return next_state(a, b, c);
}

#if defined(SAMPLE_BEHAVIOR_LIBRARY)
__attribute__((visibility("default"))) int32_t sample_invoke(int32_t a, int32_t b, int32_t c) {
    return sample_probe(a, b, c);
}
#else
int main(void) {
    if (sample_probe(STATE_OFF, 100, 0) != STATE_CRANKING) {
        return 1;
    }
    if (sample_probe(STATE_CRANKING, 700, 0) != STATE_RUNNING) {
        return 2;
    }
    if (sample_probe(STATE_RUNNING, 700, 1) != STATE_FAULT) {
        return 3;
    }
    return 0;
}
#endif
