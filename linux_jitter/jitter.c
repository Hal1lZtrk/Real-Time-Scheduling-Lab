/*
 * jitter.c - how late does a periodic Linux task wake up?
 *
 * A "scan cycle" thread sleeps until absolute times t0 + k*T
 * (clock_nanosleep with TIMER_ABSTIME, so errors do not accumulate) and
 * records how late it actually woke up. Optionally:
 *   --fifo PRIO   run the cycle thread with SCHED_FIFO (needs root / CAP_SYS_NICE)
 *   --load N      start N busy-loop threads that compete for the CPUs
 *
 * Output (stdout): one line per cycle, wake-up latency in microseconds.
 * Summary (stderr): min / mean / p99 / max.
 *
 * Build:  gcc -std=gnu11 -O2 -Wall -Wextra -o jitter jitter.c -lpthread
 * Run:    ./jitter --period-us 10000 --seconds 30 > lat_normal.csv
 *         sudo ./jitter --period-us 10000 --seconds 30 --fifo 80 --load 4 > lat_fifo_load.csv
 */
#define _GNU_SOURCE
#include <errno.h>
#include <pthread.h>
#include <sched.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define NS_PER_SEC 1000000000L

static atomic_int stop_load = 0;

static void *busy(void *arg)
{
    (void)arg;
    volatile unsigned long x = 0;
    while (!atomic_load_explicit(&stop_load, memory_order_relaxed))
        x++;
    return NULL;
}

static void add_ns(struct timespec *t, long ns)
{
    t->tv_nsec += ns;
    while (t->tv_nsec >= NS_PER_SEC) {
        t->tv_nsec -= NS_PER_SEC;
        t->tv_sec++;
    }
}

static long diff_ns(const struct timespec *a, const struct timespec *b)
{
    return (a->tv_sec - b->tv_sec) * NS_PER_SEC + (a->tv_nsec - b->tv_nsec);
}

static int cmp_long(const void *a, const void *b)
{
    long x = *(const long *)a, y = *(const long *)b;
    return (x > y) - (x < y);
}

int main(int argc, char **argv)
{
    long period_us = 10000;
    int seconds = 10, fifo_prio = 0, load = 0;

    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--period-us") && i + 1 < argc) period_us = atol(argv[++i]);
        else if (!strcmp(argv[i], "--seconds") && i + 1 < argc) seconds = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--fifo") && i + 1 < argc) fifo_prio = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--load") && i + 1 < argc) load = atoi(argv[++i]);
        else {
            fprintf(stderr, "usage: %s [--period-us N] [--seconds N] [--fifo PRIO] [--load N]\n", argv[0]);
            return 2;
        }
    }
    if (period_us <= 0 || seconds <= 0 || load < 0) {
        fprintf(stderr, "invalid arguments\n");
        return 2;
    }

    pthread_t loaders[64];
    if (load > 64) load = 64;
    for (int i = 0; i < load; i++)
        pthread_create(&loaders[i], NULL, busy, NULL);

    if (fifo_prio > 0) {
        struct sched_param sp = { .sched_priority = fifo_prio };
        int rc = pthread_setschedparam(pthread_self(), SCHED_FIFO, &sp);
        if (rc != 0) {
            fprintf(stderr, "warning: SCHED_FIFO %d not granted (%s); running as normal task\n",
                    fifo_prio, strerror(rc));
            fifo_prio = 0;
        }
    }

    long n = (long)seconds * 1000000L / period_us;
    long *lat = malloc(sizeof(long) * (size_t)n);
    if (!lat) return 1;

    struct timespec next, now;
    clock_gettime(CLOCK_MONOTONIC, &next);
    add_ns(&next, 100 * 1000 * 1000L); /* start 100 ms from now */

    long done = 0;
    for (long k = 0; k < n; k++) {
        int rc;
        while ((rc = clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &next, NULL)) == EINTR)
            ;
        clock_gettime(CLOCK_MONOTONIC, &now);
        lat[k] = diff_ns(&now, &next) / 1000; /* us late */
        done++;
        add_ns(&next, period_us * 1000L);
    }

    atomic_store(&stop_load, 1);
    for (int i = 0; i < load; i++)
        pthread_join(loaders[i], NULL);

    printf("cycle,latency_us\n");
    for (long k = 0; k < done; k++)
        printf("%ld,%ld\n", k, lat[k]);

    long *sorted = malloc(sizeof(long) * (size_t)done);
    if (!sorted) return 1;
    memcpy(sorted, lat, sizeof(long) * (size_t)done);
    qsort(sorted, (size_t)done, sizeof(long), cmp_long);
    double sum = 0;
    for (long k = 0; k < done; k++) sum += (double)lat[k];
    fprintf(stderr,
            "period=%ld us cycles=%ld policy=%s load_threads=%d\n"
            "latency us: min=%ld mean=%.1f p99=%ld max=%ld\n",
            period_us, done, fifo_prio ? "SCHED_FIFO" : "normal", load,
            sorted[0], sum / (double)done, sorted[(long)(0.99 * (double)(done - 1))], sorted[done - 1]);
    free(lat);
    free(sorted);
    return 0;
}
