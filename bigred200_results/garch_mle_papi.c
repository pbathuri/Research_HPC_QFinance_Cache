/*
 * garch_mle_papi.c
 *
 * PAPI-instrumented GARCH(1,1) log-likelihood evaluation.
 *
 *   sigma^2_t = omega + alpha * r^2_{t-1} + beta * sigma^2_{t-1}
 *   L(theta) = -0.5 * sum_{t=1}^{T} [ log(sigma^2_t) + r^2_t / sigma^2_t ]
 *
 * Evaluates log-likelihood on a parameter grid (simulating MLE optimiser).
 *
 * Usage:  ./garch_mle  <T>  <N_EVAL>
 *
 * Output (stdout, one CSV line):
 *   kernel,T,n_eval,gflops,l1_miss,seconds
 *
 * Uses PAPI high-level API (proven on BigRed200).
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

__attribute__((noipa))
void do_not_optimize_d(double *_) { (void)_; }
static volatile double sink;

/* ---- xorshift PRNG ---------------------------------------------- */
static unsigned long long xor_state = 0xABCDEF0123456789ULL;

static inline unsigned long long xorshift64(void)
{
    unsigned long long x = xor_state;
    x ^= x << 13;
    x ^= x >> 7;
    x ^= x << 17;
    xor_state = x;
    return x;
}

static inline double uniform01_d(void)
{
    return (double)(xorshift64() & 0xFFFFFFFFFFFFULL) / (double)0x1000000000000ULL;
}

static inline double randn_d(void)
{
    double u1 = uniform01_d();
    double u2 = uniform01_d();
    if (u1 < 1e-30) u1 = 1e-30;
    return sqrt(-2.0 * log(u1)) * cos(6.283185307179586 * u2);
}

/* ---- generate synthetic GARCH(1,1) return series ---------------- */
static void generate_returns(double *r, int T,
                             double omega, double alpha, double beta)
{
    double sigma2 = omega / (1.0 - alpha - beta);
    for (int t = 0; t < T; t++) {
        double z = randn_d();
        r[t] = sqrt(sigma2) * z;
        sigma2 = omega + alpha * r[t] * r[t] + beta * sigma2;
    }
}

/* ---- single log-likelihood evaluation --------------------------- */
static double garch_loglik(const double *r, int T,
                           double omega, double alpha, double beta)
{
    double sigma2 = omega / (1.0 - alpha - beta);
    double ll = 0.0;
    for (int t = 0; t < T; t++) {
        sigma2 = omega + alpha * r[t] * r[t] + beta * sigma2;
        ll -= 0.5 * (log(sigma2) + r[t] * r[t] / sigma2);
    }
    return ll;
}

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
    assert(argc == 3);
    int T      = atoi(argv[1]);
    int n_eval = atoi(argv[2]);
    assert(T > 0 && n_eval > 0);

    double *r = (double *)malloc((size_t)T * sizeof(double));
    assert(r);

    double omega_true = 0.00001;
    double alpha_true = 0.05;
    double beta_true  = 0.90;

    generate_returns(r, T, omega_true, alpha_true, beta_true);

    /* ---- PAPI HL setup ---- */
    int ret = PAPI_library_init(PAPI_VER_CURRENT);
    if (ret != PAPI_VER_CURRENT)
        fprintf(stderr, "PAPI init warning: %d\n", ret);

    char papi_dir[256];
    snprintf(papi_dir, sizeof(papi_dir), "papi_out_garch_%d_%d_%d",
             T, n_eval, (int)getpid());
    setenv("PAPI_OUTPUT_DIRECTORY", papi_dir, 1);

    /* pre-build parameter grid */
    int grid_side = (int)cbrt((double)n_eval);
    if (grid_side < 1) grid_side = 1;

    double *omegas = (double *)malloc(grid_side * sizeof(double));
    double *alphas = (double *)malloc(grid_side * sizeof(double));
    double *betas  = (double *)malloc(grid_side * sizeof(double));
    assert(omegas && alphas && betas);

    for (int i = 0; i < grid_side; i++) {
        double frac = (double)i / (double)(grid_side > 1 ? grid_side - 1 : 1);
        omegas[i] = 0.000005 + frac * 0.00002;
        alphas[i] = 0.02     + frac * 0.08;
        betas[i]  = 0.85     + frac * 0.10;
    }

    double best_ll = -1e30;
    int actual_evals = 0;
    struct timespec t0, t1;

    /* ---- timed region ---- */
    PAPI_hl_region_begin("garch_mle");
    clock_gettime(CLOCK_MONOTONIC, &t0);

    for (int io = 0; io < grid_side; io++)
      for (int ia = 0; ia < grid_side; ia++)
        for (int ib = 0; ib < grid_side; ib++) {
            double om = omegas[io];
            double al = alphas[ia];
            double be = betas[ib];
            if (al + be >= 1.0) continue;
            double ll = garch_loglik(r, T, om, al, be);
            actual_evals++;
            if (ll > best_ll)
                best_ll = ll;
        }

    clock_gettime(CLOCK_MONOTONIC, &t1);
    PAPI_hl_region_end("garch_mle");

    do_not_optimize_d(&best_ll);
    sink = best_ll;

    double seconds = (double)(t1.tv_sec - t0.tv_sec)
                   + (double)(t1.tv_nsec - t0.tv_nsec) * 1e-9;
    double flops   = 7.0 * (double)T * (double)actual_evals;
    double gflops  = (flops / seconds) * 1e-9;

    PAPI_hl_stop();
    long long l1_miss = parse_papi_l1(papi_dir);

    printf("garch_mle,%d,%d,%.15g,%lld,%.15g\n",
           T, actual_evals, gflops, l1_miss, seconds);

    /* clean up */
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

    free(betas);
    free(alphas);
    free(omegas);
    free(r);
    return 0;
}
