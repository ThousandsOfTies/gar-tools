#include "rotary_decoder.h"
#include <assert.h>
#include <stdio.h>

static int sequence(struct rotary_decoder *decoder, const unsigned *phases, unsigned count) {
    int result = 0;
    for (unsigned i = 0; i < count; i++) result += rotary_decode(decoder, phases[i]);
    return result;
}
int main(void) {
    struct rotary_decoder decoder = {3, 0};
    const unsigned clockwise[] = {1,0,2,3}, counterclockwise[] = {2,0,1,3};
    const unsigned bounced[] = {1,3,1,0,1,0,2,0,2,3};
    const unsigned incomplete[] = {1,0,1,3};
    const unsigned invalid[] = {0,2,3};
    for (unsigned i = 0; i < 100; i++) {
        assert(sequence(&decoder, clockwise, 4) == 1);
        assert(sequence(&decoder, counterclockwise, 4) == -1);
    }
    assert(sequence(&decoder, bounced, 10) == 1);
    assert(sequence(&decoder, incomplete, 4) == 0);
    assert(sequence(&decoder, invalid, 3) == 0);
    assert(sequence(&decoder, clockwise, 4) == 1);
    puts("PASS: full detents, reverse direction, contact bounce, incomplete and invalid transitions");
    return 0;
}
