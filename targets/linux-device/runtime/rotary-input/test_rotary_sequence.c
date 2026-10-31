#include "rotary_decoder.h"
#include "rotary_sequence.h"
#include <assert.h>
#include <stdio.h>

static void loss_detection(void) {
    struct rotary_sequences sequences = {{0}};
    assert(!rotary_sequence_lost(&sequences, 0, 1));
    assert(!rotary_sequence_lost(&sequences, 1, 1));
    assert(!rotary_sequence_lost(&sequences, 0, 2));
    assert(rotary_sequence_lost(&sequences, 0, 4)); /* A queued event was lost. */
    assert(!rotary_sequence_lost(&sequences, 0, 5));
    assert(!rotary_sequence_lost(&sequences, 1, 2)); /* Independent line. */
    assert(rotary_sequence_lost(&sequences, 2, 3)); /* Loss before first read. */
    sequences.last[0] = UINT32_MAX;
    assert(!rotary_sequence_lost(&sequences, 0, 0));
    assert(!rotary_sequence_lost(&sequences, 0, 1));
}

/* Replay actual GPIO v2 events. The old request-wide loss check discarded 18
 * of these 20 detents. Each line's delivered sequence is contiguous. */
static void captured_trace(const char *path) {
    FILE *file = fopen(path, "r");
    assert(file);
    char header[128];
    assert(fgets(header, sizeof(header), file));
    struct rotary_sequences sequences = {{0}};
    struct rotary_decoder decoder = {3, 0};
    unsigned bits = 7, positive = 0, negative = 0, presses = 0, edges = 0;
    unsigned last_request = 0, request_gaps = 0;
    unsigned id, line, request_sequence, line_sequence;
    int fields;
    while ((fields = fscanf(file, "%u,%u,%u,%u", &id, &line, &request_sequence, &line_sequence)) == 4) {
        assert(line < 3 && (id == 1 || id == 2));
        if (last_request && request_sequence != last_request + 1) request_gaps++;
        last_request = request_sequence;
        assert(!rotary_sequence_lost(&sequences, line, line_sequence));
        unsigned before = bits;
        if (id == 1) bits |= 1u << line;
        else bits &= ~(1u << line);
        if (line < 2) {
            unsigned phase = ((bits & 1) ? 2u : 0u) | ((bits & 2) ? 1u : 0u);
            int direction = rotary_decode(&decoder, phase);
            positive += direction == 1;
            negative += direction == -1;
        } else if ((before & 4) && !(bits & 4)) presses++;
        edges++;
    }
    assert(fields == EOF && feof(file));
    fclose(file);
    assert(edges == 112 && request_gaps == 46);
    assert(positive == 10 && negative == 10 && presses == 1);
}

int main(int argc, char **argv) {
    assert(argc == 2);
    loss_detection();
    captured_trace(argv[1]);
    puts("PASS: per-line loss, first-read loss, wraparound and 20 captured Lyra detents");
    return 0;
}
