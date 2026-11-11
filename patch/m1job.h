/* A worker thread that owns its state, and the box the UI thread posts to (patch/sbdl.c is the first user).
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * The UI thread never changes what the worker owns: it posts a message (m1_job_post) and returns. The worker takes the messages in the order they were posted (m1_job_first, then
 * m1_job_done once the message is applied, so a reader that looks at the box first and at the worker's state second misses nothing) and ends when the box is empty (m1_job_end). The
 * thread is made by the post that finds none and is detached; "no thread runs" always means "the box is empty", so a post is never left behind by a worker that is ending.
 *
 * A message is a struct of the caller's that starts with m1_msg_t; the worker frees it after m1_job_done (the box never does). The lock is a spin lock held for a few instructions; the caller may take it
 * (m1_job_lock) to guard its own small state and to walk the box from head.
 */
#pragma once
#include "stock.h"

typedef struct m1_msg {
    struct m1_msg *next;
    int op;
} m1_msg_t;

typedef struct {
    volatile int lock;
    int busy; /* a worker thread runs (or is being made) */
    m1_msg_t *head, *tail;
} m1_job_t;

static inline void m1_job_lock(m1_job_t *j) {
    while (__sync_lock_test_and_set(&j->lock, 1)) {
    }
}
static inline void m1_job_unlock(m1_job_t *j) { __sync_lock_release(&j->lock); }

/* UI thread: msg goes to the end of the box; `main` is started when no worker runs. 0, or -1 when the thread could not be made: msg is out of the box again and still the caller's
 * (no worker runs then, so the caller may do the message's work itself). */
static inline int m1_job_post(m1_job_t *j, m1_msg_t *msg, void *(*main)(void *)) {
    unsigned long th = 0;
    int start;
    msg->next = (m1_msg_t *)0;
    m1_job_lock(j);
    if (j->tail)
        j->tail->next = msg;
    else
        j->head = msg;
    j->tail = msg;
    start = !j->busy;
    if (start) j->busy = 1;
    m1_job_unlock(j);
    if (!start) return 0;
    if (pthread_create(&th, (const void *)0, main, (void *)0)) {
        m1_job_lock(j);
        j->head = j->tail = (m1_msg_t *)0; /* (no worker ran, so the box held this message only) */
        j->busy = 0;
        m1_job_unlock(j);
        return -1;
    }
    pthread_detach(th);
    return 0;
}

/* Worker: the oldest message, still in the box; NULL when there is none. */
static inline m1_msg_t *m1_job_first(m1_job_t *j) {
    m1_msg_t *m;
    m1_job_lock(j);
    m = j->head;
    m1_job_unlock(j);
    return m;
}

/* Worker: the oldest message is applied: out of the box. It is the worker's to free (or to keep, when it is not an allocated one). */
static inline void m1_job_done(m1_job_t *j) {
    m1_msg_t *m;
    m1_job_lock(j);
    m = j->head;
    if (m) {
        j->head = m->next;
        if (!j->head) j->tail = (m1_msg_t *)0;
    }
    m1_job_unlock(j);
}

/* Worker: 1 when the box is empty: the worker is marked ended and must return without touching its state again; 0 when a message came meanwhile. */
static inline int m1_job_end(m1_job_t *j) {
    int end;
    m1_job_lock(j);
    end = !j->head;
    if (end) j->busy = 0;
    m1_job_unlock(j);
    return end;
}
