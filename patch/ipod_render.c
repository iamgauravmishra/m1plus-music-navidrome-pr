/* A display model owns strings and (only while moving) cloned images. Paint never allocates.
 * The stock framebuffer is not sampled. No borrowed library record survives a query.
 * MIT, Copyright (c) 2026 Xin. */
#include "stock.h"
#include "offsets.inc"
#include "ipod_render.h"

#define COMMANDS 192
#define TEXT_WORDS 2048
#define IMAGES 8
#define SLIDE_MS 280 /* the reference's push and pop: 280 ms ease in and out */
#define I(p, o) (*(int *)((char *)(p) + (o)))

enum { DRAW_FILL, DRAW_TEXT, DRAW_IMAGE };
struct command {
    int kind, rect[4], src[4],
        edge; /* edge: the image is the menu half's edge shadow (ip_render_edge): it belongs to the left half of a split */
    unsigned color, text, n;
    void *style, *bitmap;
};
struct picture {
    struct command commands[COMMANDS];
    unsigned text[TEXT_WORDS];
    unsigned count, used;
    int valid;
};
static struct {
    struct picture *last, *old;
    void *style, *edge, *images[IMAGES];
    unsigned nimages, start, elapsed;
    int recording, overflow, active, direction, width, split;
} render __attribute__((section(".scratch")));

static void clear_old(void) {
    unsigned i;
    for (i = 0; i < render.nimages; ++i) bitmap_destroy(render.images[i]);
    render.nimages = 0;
    render.active = 0;
}

void ip_render_cancel(void) {
    clear_old();
    if (render.last) render.last->valid = 0;
}

void ip_render_close(void) {
    clear_old();
    if (render.last) free(render.last);
    if (render.old) free(render.old);
    memset(&render, 0, sizeof render);
}

void ip_render_open(void) {
    ip_render_close();
    render.last = calloc(1, sizeof(struct picture));
    render.old = calloc(1, sizeof(struct picture));
    if (!render.last || !render.old) ip_render_close();
}

static void *clone(void *source) {
    unsigned w = (unsigned)I(source, 0), h = (unsigned)I(source, 4), pitch, y;
    const unsigned char *src;
    unsigned char *dst;
    void *copy;
    if (!w || !h || w > 320 || h > 264 || *(unsigned short *)((char *)source + BITMAP_FORMAT) != BITMAP_RGBA8888)
        return (void *)0;
    pitch = bitmap_get_line_length(source);
    if (pitch < w * 4) return (void *)0;
    copy = bitmap_create_ex(w, h, w * 4, BITMAP_RGBA8888);
    if (!copy) return (void *)0;
    src = bitmap_lock_buffer_for_read(source);
    dst = bitmap_lock_buffer_for_write(copy);
    if (src && dst)
        for (y = 0; y < h; ++y) memcpy(dst + y * w * 4, src + y * pitch, w * 4);
    if (src) bitmap_unlock_buffer(source);
    if (dst) bitmap_unlock_buffer(copy);
    if (!src || !dst) {
        bitmap_destroy(copy);
        return (void *)0;
    }
    return copy;
}

int ip_render_transition(int direction, int width) {
    void *original[IMAGES];
    unsigned i, j;
    /* Fast input settles immediately, rather than stacking transitions or snapshots. */
    if (render.active) {
        ip_render_cancel();
        return 0;
    }
    if (!render.last || !render.old || !render.last->valid) return 0;
    memcpy(render.old, render.last, sizeof(struct picture));
    /* width 0: the split. The menu half and the artwork pane of a split page part (opening a fullscreen page) or close over it; every command is kept. */
    render.split = width == 0;
    if (render.split) width = IP_SPLIT_X;
    /* Half-width navigation does not move or clone the stationary artwork pane. */
    for (i = 0, j = 0; i < render.old->count; ++i) {
        if (render.split) {
            j = render.old->count;
            break;
        }
        struct command *c = &render.old->commands[i];
        if (c->rect[0] >= width || c->rect[0] + c->rect[2] <= 0) continue;
        if (i != j) memcpy(&render.old->commands[j], c, sizeof *c);
        ++j;
    }
    render.old->count = j;
    for (i = 0; i < render.old->count; ++i) {
        struct command *c = &render.old->commands[i];
        if (c->kind != DRAW_IMAGE) continue;
        for (j = 0; j < render.nimages; ++j)
            if (original[j] == c->bitmap) break;
        if (j == render.nimages) {
            void *copy;
            if (j >= IMAGES || !(copy = clone(c->bitmap))) {
                ip_render_cancel();
                return 0;
            }
            original[j] = c->bitmap;
            render.images[render.nimages++] = copy;
        }
        c->bitmap = render.images[j];
    }
    render.direction = direction;
    render.width = width;
    render.start = time_now_ms();
    render.elapsed = 0;
    render.active = 1;
    render.last->valid = 0;
    return 1;
}

int ip_render_active(void) { return render.active; }
int ip_render_width(void) { return render.width; }
int ip_render_split(void) { return render.active && render.split; }
int ip_render_direction(void) { return render.direction; }
void ip_render_edge(void *bitmap) {
    render.edge = bitmap;
} /* the menu edge's shadow image: recorded images that are it replay with the menu half */

int ip_render_tick(void) {
    if (!render.active) return 0;
    render.elapsed = time_now_ms() - render.start;
    if (render.elapsed >= SLIDE_MS) clear_old();
    return 1;
}

void ip_render_offsets(int *outgoing, int *incoming) {
    unsigned p = render.elapsed * 1024 / SLIDE_MS;
    unsigned eased = (p * p / 1024) * (3072 - 2 * p) / 1024;
    int travel = (int)(render.width * eased / 1024);
    *outgoing = render.direction > 0 ? -travel : travel;
    *incoming = render.direction > 0 ? render.width - travel : travel - render.width;
}

void ip_render_begin(void) {
    if (!render.last) return;
    render.last->count = render.last->used = 0;
    render.last->valid = 0;
    render.overflow = 0;
    render.recording = 1;
}

void ip_render_end(void) {
    render.recording = 0;
    if (render.last) render.last->valid = !render.overflow;
}

static struct command *append(int kind, const int *rect) {
    struct command *c;
    if (!render.recording || !render.last) return (struct command *)0;
    if (render.last->count == COMMANDS) {
        render.overflow = 1;
        return (struct command *)0;
    }
    c = &render.last->commands[render.last->count++];
    c->kind = kind, c->edge = 0;
    memcpy(c->rect, rect, 4 * sizeof(int));
    return c;
}

void ip_render_prepare(void *style, void *canvas) {
    render.style = style;
    widget_prepare_text_style(style, canvas);
}

void ip_render_fill(void *canvas, int x, int y, int w, int h, unsigned rgb) {
    int rect[4] = {x, y, w, h};
    struct command *c = append(DRAW_FILL, rect);
    if (c) c->color = rgb;
    canvas_set_fill_color(canvas, 0xff000000u | rgb);
    canvas_fill_rect(canvas, x, y, w, h);
}

void ip_render_text(void *canvas, const unsigned *text, unsigned n, const int *rect) {
    struct command *c = append(DRAW_TEXT, rect);
    if (c) {
        if (n > TEXT_WORDS - render.last->used) {
            render.overflow = 1;
            --render.last->count;
        } else {
            c->text = render.last->used, c->n = n, c->style = render.style;
            memcpy(render.last->text + c->text, text, n * sizeof(unsigned));
            render.last->used += n;
        }
    }
    canvas_draw_text_in_rect(canvas, text, n, rect);
}

void ip_render_image(void *canvas, void *bitmap, const int *src, const int *dst) {
    struct command *c = append(DRAW_IMAGE, dst);
    if (c) {
        c->bitmap = bitmap;
        c->edge = bitmap == render.edge;
        memcpy(c->src, src, 4 * sizeof(int));
    }
    canvas_draw_image(canvas, bitmap, src, dst);
}

void ip_render_out(void *canvas, int half) {
    unsigned i;
    if (!render.active || !render.old) return;
    for (i = 0; i < render.old->count; ++i) {
        const struct command *c = &render.old->commands[i];
        if (half < 2 && (!c->edge && c->rect[0] >= IP_SPLIT_X) != half) continue;
        if (c->kind == DRAW_FILL) {
            canvas_set_fill_color(canvas, 0xff000000u | c->color);
            canvas_fill_rect(canvas, c->rect[0], c->rect[1], c->rect[2], c->rect[3]);
        } else if (c->kind == DRAW_TEXT) {
            widget_prepare_text_style(c->style, canvas);
            canvas_draw_text_in_rect(canvas, render.old->text + c->text, c->n, c->rect);
        } else
            canvas_draw_image(canvas, c->bitmap, c->src, c->rect);
    }
}
