#ifndef GAR_ROTARY_DECODER_H
#define GAR_ROTARY_DECODER_H

/* A full quadrature detent starts/ends with both contacts high. Contact bounce
 * cancels itself; incomplete or diagonal transitions must not select a step. */
struct rotary_decoder { unsigned phase; int quarter_steps; };
static inline int rotary_decode(struct rotary_decoder *decoder, unsigned phase) {
    static const int transitions[16] = {0,-1,1,0, 1,0,0,-1, -1,0,0,1, 0,1,-1,0};
    unsigned previous = decoder->phase;
    decoder->phase = phase;
    if ((previous ^ phase) == 3) decoder->quarter_steps = 0;
    else decoder->quarter_steps += transitions[(previous << 2) | phase];
    if (phase != 3) return 0;
    int direction = decoder->quarter_steps == 4 ? 1 : decoder->quarter_steps == -4 ? -1 : 0;
    decoder->quarter_steps = 0;
    return direction;
}
#endif
