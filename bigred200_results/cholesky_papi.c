/*
 * cholesky_papi.c
 *
 * PAPI-instrumented Cholesky decomposition of a synthetic SPD matrix.
 *
 * Compile-time selection:
 *   Layout:    -DROW_MAJOR  or  -DCOL_MAJOR
 *   Algorithm: -DALGO_BANACHIEWICZ (row-by-row)
 *              -DALGO_CROUT        (column-by-column)
 *
 * Usage:  ./cholesky_<layout>_<algo>  <d>
 *
 * Prints one CSV line to stdout:
 *   layout,algo,d,gflops,l1_miss,seconds
 *
 * Uses PAPI high-level API (same as mm_papi.c which is proven on BigRed200).
 * L1 miss count is extracted from PAPI_hl output via environment variables.
 */

#include <assert.h>
#include <dirent.h>
#include <math.h>
#include <papi.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

/* ---- layout ---------------------------------------------------- */
#if defined(ROW_MAJOR)
  #define IDX(i,j,n) ((i)*(n) + (j))
  #define LAYOUT_STR "rm"
#elif defined(COL_MAJOR)
  #define IDX(i,j,n) ((i) + (j)*(n))
  #define LAYOUT_STR "cm"
#else
  #error "Define ROW_MAJOR or COL_MAJOR"
#endif

#if defined(ALGO_BANACHIEWICZ)
  #define ALGO_STR "banachiewicz"
#elif defined(ALGO_CROUT)
  #define ALGO_STR "crout"
#else
  #error "Define ALGO_BANACHIEWICZ or ALGO_CROUT"
#endif

__attribute__((noipa))
void do_not_optimize(float *_) { (void)_; }
static volatile float sink_f;

/* ---- build random SPD matrix: A = M M^T + d·I ------------------- */
static void build_spd(float *A, int d)
{
    float *M = (float *)calloc((size_t)d * d, sizeof(float));
    assert(M);
    srand(42);
    for (int i = 0; i < d; i++)
        for (int j = 0; j < d; j++)
            M[IDX(i, j, d)] = (float)(rand() % 1024 + 1) / 1024.0f;
    for (int i = 0; i < d; i++)
        for (int j = 0; j <= i; j++) {
            float s = 0.0f;
            for (int k = 0; k < d; k++)
                s += M[IDX(i, k, d)] * M[IDX(j, k, d)];
            A[IDX(i, j, d)] = s;
            A[IDX(j, i, d)] = s;
        }
    for (int i = 0; i < d; i++)
        A[IDX(i, i, d)] += (float)d;
    free(M);
}

/* ---- Banachiewicz (row-by-row) ---------------------------------- */
#if defined(ALGO_BANACHIEWICZ)
static void cholesky(float *L, const float *A, int d)
{
    for (int i = 0; i < d; i++) {
        for (int j = 0; j <= i; j++) {
            float sum = 0.0f;
            for (int k = 0; k < j; k++)
                sum += L[IDX(i, k, d)] * L[IDX(j, k, d)];
            if (i == j)
                L[IDX(i, j, d)] = sqrtf(A[IDX(i, j, d)] - sum);
            else
                L[IDX(i, j, d)] = (A[IDX(i, j, d)] - sum) / L[IDX(j, j, d)];
        }
    }
}
#endif

/* ---- Crout (column-by-column) ----------------------------------- */
#if defined(ALGO_CROUT)
static void cholesky(float *L, const float *A, int d)
{
    for (int j = 0; j < d; j++) {
        float sum = 0.0f;
        for (int k = 0; k < j; k++)
            sum += L[IDX(j, k, d)] * L[IDX(j, k, d)];
        L[IDX(j, j, d)] = sqrtf(A[IDX(j, j, d)] - sum);
        float ljj = L[IDX(j, j, d)];
        for (int i = j + 1; i < d; i++) {
            float s = 0.0f;
            for (int k = 0; k < j; k++)
                s += L[IDX(i, k, d)] * L[IDX(j, k, d)];
            L[IDX(i, j, d)] = (A[IDX(i, j, d)] - s) / ljj;
        }
    }
}
#endif

/* ---- parse PAPI HL JSON output for L1_DCM ----------------------- */
static long long parse_papi_l1(const char *outdir)
{
    long long val = -1;
    DIR *dp = opendir(outdir);
    if (!dp) return val;
    struct dirent *ent;
    char path[1024];
    while ((ent = readdir(dp)) != NULL) {
        if (strstr(ent->d_name, ".json") == NULL) continue;
        snprintf(path, sizeof(path), "%s/%s", outdir, ent->d_name);
        FILE *f = fopen(path, "r");
        if (!f) continue;
        char buf[4096];
        while (fgets(buf, sizeof(buf), f)) {
            char *p = strstr(buf, "PAPI_L1_DCM");
            if (p) {
                p = strchr(p, ':');
                if (p) val = atoll(p + 1);
            }
        }
        fclose(f);
    }
    closedir(dp);
    return val;
}

/* ----------------------------------------------------------------- */
int main(int argc, char **argv)
{
    assert(argc == 2);
    int d = atoi(argv[1]);
    assert(d > 0);

    size_t n2 = (size_t)d * d;
    float *A = (float *)calloc(n2, sizeof(float));
    float *L = (float *)calloc(n2, sizeof(float));
    assert(A && L);

    build_spd(A, d);

    /* ---- PAPI high-level setup ---- */
    int ret = PAPI_library_init(PAPI_VER_CURRENT);
    if (ret != PAPI_VER_CURRENT)
        fprintf(stderr, "PAPI init warning: %d\n", ret);

    /* Use a unique output dir per invocation */
    char papi_dir[256];
    snprintf(papi_dir, sizeof(papi_dir), "papi_out_%s_%s_%d_%d",
             LAYOUT_STR, ALGO_STR, d, (int)getpid());
    setenv("PAPI_OUTPUT_DIRECTORY", papi_dir, 1);

    struct timespec t0, t1;

    /* ---- timed region (PAPI HL wraps the same region) ---- */
    PAPI_hl_region_begin("cholesky");
    clock_gettime(CLOCK_MONOTONIC, &t0);

    cholesky(L, A, d);

    clock_gettime(CLOCK_MONOTONIC, &t1);
    PAPI_hl_region_end("cholesky");

    do_not_optimize(L);
    sink_f = L[0];

    double seconds = (double)(t1.tv_sec - t0.tv_sec)
                   + (double)(t1.tv_nsec - t0.tv_nsec) * 1e-9;
    double flops   = (double)d * (double)d * (double)d / 3.0;
    double gflops  = (flops / seconds) * 1e-9;

    /* Force PAPI to flush output */
    PAPI_hl_stop();

    long long l1_miss = parse_papi_l1(papi_dir);

    printf("%s,%s,%d,%.15g,%lld,%.15g\n",
           LAYOUT_STR, ALGO_STR, d, gflops, l1_miss, seconds);

    /* clean up papi output dir */
    {
        DIR *dp = opendir(papi_dir);
        if (dp) {
            struct dirent *ent;
            char path[1024];
            while ((ent = readdir(dp)) != NULL) {
                if (ent->d_name[0] == '.') continue;
                snprintf(path, sizeof(path), "%s/%s", papi_dir, ent->d_name);
                remove(path);
            }
            closedir(dp);
            rmdir(papi_dir);
        }
    }

    free(L);
    free(A);
    return 0;
}
