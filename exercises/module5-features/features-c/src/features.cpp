// Module 5 Track B — feature implementations for the nRF52840 (Cortex-M4F).
// See features.h for the conventions shared with the Python reference.

#include "features.h"
#include <math.h>
#include <string.h>

#ifndef USE_NAIVE_DFT
// VERIFY: arm_math.h must resolve via the CMSIS-DSP lib_deps entry (see
// platformio.ini). If the build fails here, add -DUSE_NAIVE_DFT to build_flags.
#include "arm_math.h"
#endif

void time_features_compute(const float *x, int n, time_features_t *out)
{
    float sum = 0.0f, sum_sq = 0.0f;
    float mn = x[0], mx = x[0];

    // one pass: sums + extremes
    for (int i = 0; i < n; i++) {
        const float v = x[i];
        sum += v;
        sum_sq += v * v;
        if (v < mn) mn = v;
        if (v > mx) mx = v;
    }

    const float mean = sum / (float)n;
    const float mean_sq = sum_sq / (float)n;
    float var = mean_sq - mean * mean;   // population variance, E[x^2] - E[x]^2
    if (var < 0.0f) var = 0.0f;          // guard tiny negative from float rounding

    out->mean = mean;
    out->std = sqrtf(var);
    out->rms = sqrtf(mean_sq);
    out->min = mn;
    out->max = mx;

    // second (short) pass: zero crossings around the mean
    int zc = 0;
    for (int i = 1; i < n; i++) {
        if ((x[i] - mean) * (x[i - 1] - mean) < 0.0f) {
            zc++;
        }
    }
    out->zero_crossings = zc;
}

// ---------------------------------------------------------------------------
// Spectral: Hann window -> real FFT -> |X|^2 summed into equal bands.
// ---------------------------------------------------------------------------

static float s_windowed[FEAT_FFT_N];

static void apply_hann(const float *x, int n, float *out)
{
    // matches numpy.hanning: 0.5 - 0.5*cos(2*pi*i/(n-1))
    const float k = 2.0f * (float)M_PI / (float)(n - 1);
    for (int i = 0; i < n; i++) {
        out[i] = x[i] * (0.5f - 0.5f * cosf(k * (float)i));
    }
}

#ifndef USE_NAIVE_DFT

static arm_rfft_fast_instance_f32 s_rfft;
static bool s_rfft_ready = false;
static float s_fft_out[FEAT_FFT_N];   // packed: [DC, Nyquist, re1, im1, re2, im2, ...]

int band_energies_compute(const float *x, int n, float fs,
                          float *bands, int n_bands)
{
    if (n != FEAT_FFT_N || n_bands <= 0 || bands == NULL) return -1;

    if (!s_rfft_ready) {
        // VERIFY: arm_rfft_fast_init_f32 returns ARM_MATH_SUCCESS for N=256 when
        // the required twiddle tables are compiled in (they are, in full CMSIS-DSP builds).
        if (arm_rfft_fast_init_f32(&s_rfft, FEAT_FFT_N) != ARM_MATH_SUCCESS) return -1;
        s_rfft_ready = true;
    }

    apply_hann(x, n, s_windowed);
    arm_rfft_fast_f32(&s_rfft, s_windowed, s_fft_out, 0 /* forward */);

    for (int b = 0; b < n_bands; b++) bands[b] = 0.0f;
    const float band_hz = (fs * 0.5f) / (float)n_bands;
    const float bin_hz = fs / (float)n;

    // CMSIS packing: s_fft_out[0] = DC (real), s_fft_out[1] = Nyquist (real),
    // then re/im pairs for k = 1 .. n/2-1. We skip DC and Nyquist — matching
    // the Python reference (freqs >= b*band_hz & < (b+1)*band_hz, sel[0]=False).
    for (int k = 1; k < n / 2; k++) {
        const float re = s_fft_out[2 * k];
        const float im = s_fft_out[2 * k + 1];
        const float freq = bin_hz * (float)k;
        int b = (int)(freq / band_hz);
        if (b >= n_bands) b = n_bands - 1;   // guard float edge cases
        bands[b] += re * re + im * im;
    }
    return 0;
}

#else  // USE_NAIVE_DFT --------------------------------------------------------

// Plain-C O(N^2) DFT fallback: numerically equivalent, ~2 orders of magnitude
// slower (still fast enough for the exercise). No external dependencies.
int band_energies_compute(const float *x, int n, float fs,
                          float *bands, int n_bands)
{
    if (n != FEAT_FFT_N || n_bands <= 0 || bands == NULL) return -1;

    apply_hann(x, n, s_windowed);

    for (int b = 0; b < n_bands; b++) bands[b] = 0.0f;
    const float band_hz = (fs * 0.5f) / (float)n_bands;
    const float bin_hz = fs / (float)n;
    const float w0 = 2.0f * (float)M_PI / (float)n;

    for (int k = 1; k < n / 2; k++) {          // skip DC and Nyquist
        float re = 0.0f, im = 0.0f;
        for (int i = 0; i < n; i++) {
            const float ang = w0 * (float)k * (float)i;
            re += s_windowed[i] * cosf(ang);
            im -= s_windowed[i] * sinf(ang);
        }
        const float freq = bin_hz * (float)k;
        int b = (int)(freq / band_hz);
        if (b >= n_bands) b = n_bands - 1;
        bands[b] += re * re + im * im;
    }
    return 0;
}

#endif // USE_NAIVE_DFT
