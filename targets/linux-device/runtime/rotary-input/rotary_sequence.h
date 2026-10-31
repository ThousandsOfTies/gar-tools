#ifndef GAR_ROTARY_SEQUENCE_H
#define GAR_ROTARY_SEQUENCE_H
#include <stdint.h>

struct rotary_sequences { uint32_t last[3]; };

/* Count delivered events on each line. Threaded GPIO IRQs can coalesce or
 * overwrite the request-wide seqno before publishing an event, even when no
 * event was dropped from the userspace queue. line_seqno is assigned when the
 * event is published, and gaps on that line still detect queue overflow. */
static inline int rotary_sequence_lost(struct rotary_sequences *sequences,
                                       unsigned line, uint32_t line_sequence) {
    uint32_t expected = sequences->last[line] + UINT32_C(1);
    sequences->last[line] = line_sequence;
    return line_sequence != expected;
}
#endif
