/* M1+ Music parametric EQ, the player's filter: hciplayer's equalizer, replaced (docs/modules/peq.md).
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 * After q2-pod's patch/peq_player.c (Copyright (c) 2026 Diamond Bond, MIT licence): the filter's control, play and uninit,
 * the DSD pass-through and the reload on stock's gain command are its.
 *
 * hciplayer is MPlayer 1.3.0 modified. tools/mod_player.py points the equalizer's af_info open slot (0x89381c, stock
 * 0x44fd14) at peq_open, so every instance the player makes of "equalizer" is this filter. Stock adds it while its
 * Equalizer switch is on (mcl-seteq, then the playback loop's 0x4291cc, again at each file) and deletes it when the
 * switch goes off, so with the switch off nothing here runs. 0x4291cc then sends GAIN SET (0x40001d00) for channels 0..7
 * with stock's ten gains (0xb10df4, dB): channel 0 rereads the state record (PEQ_STATE) and plays its curve, the file's
 * preset or the 10-Band EQ's gains and preamp (the record's, not stock's) as peaking bands, through the engine's 20 ms ramp. Control runs on the playback loop, never
 * in the PCM callback. The kill switch (PEQ_KILL, read at each open) passes everything through.
 *
 * Filter memory across a gapless join (the idea and the guards are q2-pod's, issue #137; the trigger is this player's):
 * every file gets a new instance (the old one's uninit, from uninit_player's acodec step, runs before the next one's open,
 * on the playback thread), and a cascade that starts from zero memory under a continuous signal clicks. An instance that
 * played to its demuxer's end leaves its settled memory in carry; the next instance adopts it on its first block when the
 * rate, the channel count and the whole curve match and the join is under CARRY_MS old. Anything else starts from zero.
 */
#include "peq.h"

_Static_assert(sizeof(af_data) == 24, "audio ABI");
_Static_assert(__builtin_offsetof(af_instance, setup) == 16, "setup ABI");
_Static_assert(__builtin_offsetof(af_instance, data) == 20, "data ABI");
_Static_assert(__builtin_offsetof(af_instance, mul) == 40, "multiplier ABI");

#define AF_CONTROL_REINIT 0x10000100
#define AF_CONTROL_COMMAND_LINE 0x20000300
#define AF_CONTROL_EQ_GAIN_SET 0x40001d00
#define AF_CONTROL_EQ_GAIN_GET 0x40001d01
#define AF_OK 1
#define AF_FALSE 0
#define AF_UNKNOWN -1
#define AF_ERROR -2
#define AF_FORMAT_FLOAT 0x1d /* AF_FORMAT_FLOAT_NE: what the engine filters */

/* mpctx (0xaf9e30, as the rate gates read it: lw -0x61d0 from lui 0xb0), its sh_audio (+0x2c), the codec (+4) and
 * the codec's name (+0x3d0) and driver (+0x3e0), as "Selected audio codec" prints them (0x47ed70). The ten gains
 * mcl-seteq parses (0xb10df4) are no longer read (the 10-Band EQ plays the record's gains). Pinned by tools/mod_player.py. */
#define MPCTX (*(char *volatile *)0xaf9e30u)

typedef struct {
    peq_dsp dsp;
    peq_preset preset;
    int off; /* the kill switch was there at the open: pass everything through */
    int fresh; /* REINIT done, no block yet: the first one may adopt the carried memory */
    int played; /* this instance has filtered a block */
} player_state;

/* The memory of the instance that just ended, in the payload's .data (no .bss here; one writer: the playback thread). */
#define CARRY_MS 3000 /* older than this (a stop, a pause, the album's end) would only ring into an unrelated start */
static struct {
    double z[PEQ_CHANNELS][PEQ_BANDS][2];
    peq_preset preset;
    long long at; /* ms, CLOCK_MONOTONIC, when it was left */
    int rate, channels, valid;
} carry __attribute__((section(".data")));

static long long now_ms(void) {
    struct {
        int sec, nsec;
    } ts;
    return clock_gettime(1, &ts) ? -1 : (long long)ts.sec * 1000 + ts.nsec / 1000000;
}

/* mpctx->d_audio (+0x34)->eof (+0x1c): the demuxer reached the file's end (MPlayer's ds->eof), not a skip or a stop. */
static int track_ended(void) {
    char *mp = MPCTX, *ds = mp ? *(char **)(mp + 0x34) : 0;
    return ds && *(volatile int *)(ds + 0x1c);
}

/* An instance that filtered at least one block is going away: keep its memory if it played its track out, in a settled
 * curve, with finite state; otherwise drop what an earlier one left (the stream has moved on). */
static void leave(player_state *s) {
    if (!s->played) return;
    carry.valid = 0;
    long long t = now_ms();
    if (s->off || !s->dsp.channels || s->dsp.current.bypass || s->dsp.ramp || s->dsp.waiting || t < 0 || !track_ended())
        return;
    for (int ch = 0; ch < PEQ_CHANNELS; ++ch)
        for (int b = 0; b < PEQ_BANDS; ++b)
            for (int k = 0; k < 2; ++k)
                if (!__builtin_isfinite(s->dsp.current.z[ch][b][k])) return;
    memcpy(carry.z, s->dsp.current.z, sizeof carry.z);
    carry.preset = s->preset;
    carry.at = t;
    carry.rate = s->dsp.rate;
    carry.channels = s->dsp.channels;
    carry.valid = 1;
}

/* The first block of a new instance: one try, and the memory is gone either way. */
static void adopt(player_state *s) {
    long long t = now_ms();
    int ok = carry.valid && t >= carry.at && t - carry.at < CARRY_MS && carry.rate == s->dsp.rate &&
             carry.channels == s->dsp.channels && !s->dsp.current.bypass && !s->dsp.waiting &&
             !memcmp(&carry.preset, &s->preset, sizeof carry.preset);
    carry.valid = 0;
    if (ok) memcpy(s->dsp.current.z, carry.z, sizeof carry.z);
}

/* DSD (the vendor's dsdiff driver: dsf, dff, SACD iso; or FFmpeg's ffdsd*) reaches the chain as integer PCM,
 * possibly DoP, whose bits must arrive unchanged: pass it through. */
static int dsd(void) {
    char *mp = MPCTX, *sh = mp ? *(char **)(mp + 0x2c) : 0, *codec = sh ? *(char **)(sh + 4) : 0;
    if (!codec) return 0;
    const char *name = *(char **)(codec + 0x3d0), *drv = *(char **)(codec + 0x3e0);
    return (drv && !strcmp(drv, "dsdiff")) || (name && strlen(name) >= 5 && !memcmp(name, "ffdsd", 5));
}

/* What plays: the record's preset (PEQ_FILE), or the 10-Band EQ's ten gains and preamp (none readable: Flat, Auto). */
static void effective(peq_preset *p) {
    peq_state s;
    if (peq_state_load(&s) && s.mode == PEQ_FILE)
        *p = s.preset;
    else
        peq_tenband(p, s.gain, s.preamp);
}

static int control(af_instance *af, int command, void *arg) {
    player_state *s = af->setup;
    if (command == AF_CONTROL_REINIT) {
        af_data *in = arg;
        if (!in || in->nch < 1 || in->nch > PEQ_CHANNELS) return AF_ERROR;
        *af->data = *in;
        if (s->off || in->rate < 8000 || in->rate > 384000 || (in->format & ~63) || dsd()) {
            s->dsp.channels = 0; /* play leaves every block alone */
            carry.valid = 0; /* nothing carries through a pass-through track */
            return AF_OK;
        }
        effective(&s->preset);
        peq_reset(&s->dsp, in->rate, in->nch, &s->preset);
        s->fresh = 1;
        af->data->format = AF_FORMAT_FLOAT;
        af->data->bps = 4;
        if (in->format != AF_FORMAT_FLOAT || in->bps != 4) {
            *in = *af->data; /* ask the chain for float */
            return AF_FALSE;
        }
        return AF_OK;
    }
    if (command == AF_CONTROL_EQ_GAIN_SET || command == AF_CONTROL_EQ_GAIN_GET) {
        struct {
            float *gain;
            int channel;
        } *ext = arg;
        if (!ext || !ext->gain || ext->channel < 0 || ext->channel >= PEQ_CHANNELS) return AF_ERROR;
        if (command == AF_CONTROL_EQ_GAIN_GET) {
            memset(ext->gain, 0, PEQ_TENBAND * sizeof(float));
        } else if (!ext->channel && !s->off && s->dsp.channels) {
            peq_preset p;
            effective(&p);
            if (memcmp(&p, &s->preset, sizeof(p)) && peq_update(&s->dsp, &p)) s->preset = p;
        }
        return AF_OK;
    }
    if (command == AF_CONTROL_COMMAND_LINE) return AF_OK;
    return AF_UNKNOWN;
}

static af_data *play(af_instance *af, af_data *data) {
    player_state *s = af->setup;
    if (data && data->len > 0 && data->format == AF_FORMAT_FLOAT && data->bps == 4 && data->nch == s->dsp.channels &&
        data->rate == s->dsp.rate && !(data->len % (4 * data->nch))) {
        if (s->fresh) {
            s->fresh = 0;
            adopt(s);
        }
        s->played = 1;
        peq_process(&s->dsp, data->audio, (unsigned)data->len / (4 * data->nch));
    }
    return data;
}

static void uninit(af_instance *af) {
    if (af->setup) leave(af->setup);
    free(af->data);
    free(af->setup);
    af->data = 0;
    af->setup = 0;
}

int peq_open(af_instance *af) {
    af->control = control;
    af->uninit = uninit;
    af->play = play;
    af->mul = 1;
    af->delay = 0;
    af->data = calloc(1, sizeof(af_data));
    af->setup = calloc(1, sizeof(player_state));
    if (!af->data || !af->setup) return AF_ERROR; /* af_create calls uninit on failure */
    void *kill = fopen(PEQ_KILL, "rb");
    if (kill) {
        ((player_state *)af->setup)->off = 1;
        fclose(kill);
    }
    return AF_OK;
}
