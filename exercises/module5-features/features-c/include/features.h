// Module 5 Track B — feature extraction API
// Conventions are locked to the Python side (notebooks/01+02, validate_features.py):
//   * std  = POPULATION standard deviation (divide by N, like numpy.std default),
//            computed two-pass as sum((x-mean)^2)/N. The one-pass E[x^2]-E[x]^2
//            identity is NOT usable here: gravity makes E[x^2] ~400x the variance
//            and float32 cancellation then costs ~4 significant digits.
//   * zero crossings = count of i in [1, N-1] where (x[i]-mean)*(x[i-1]-mean) < 0
//   * band energies  = Hann-windowed real FFT, |X[k]|^2 summed into n_bands equal
//                      bands over [0, fs/2); DC bin (k=0) and Nyquist bin excluded.
//     Hann: w[i] = 0.5 - 0.5*cos(2*pi*i/(N-1))   (matches numpy.hanning)
// Change a convention on one side only and the validation script WILL fail — by design.

#pragma once
#include <stdint.h>

// FFT length; also the golden-window length. Must match FFT_N in notebook 02
// section 8 (which exports the golden windows) — power of two for the CMSIS rfft.
#define FEAT_FFT_N   512
// Bands are always fs/2 split into FEAT_N_BANDS equal slices, so their width
// follows the sample rate: 25 Hz each at fs = 250 Hz (the Module 4 convention).
#define FEAT_N_BANDS 5

typedef struct {
    float mean;
    float std;   // population
    float rms;
    float min;
    float max;
    int   zero_crossings;
} time_features_t;

#ifdef __cplusplus
extern "C" {
#endif

// Single pass over x[0..n-1] (plus one short pass for zero crossings).
// No dynamic allocation.
void time_features_compute(const float *x, int n, time_features_t *out);

// n must equal FEAT_FFT_N. Writes n_bands energies into bands[].
// Returns 0 on success, -1 on bad arguments.
// Default entry point: uses CMSIS-DSP when built with -DUSE_CMSIS_DSP, else the
// plain-C DFT. Both produce identical band energies (validated to < 1e-3).
int band_energies_compute(const float *x, int n, float fs,
                          float *bands, int n_bands);

// Explicit backends, exposed so main.cpp can time them head-to-head.
// band_energies_naive is always available (no external deps); band_energies_cmsis
// exists only in a -DUSE_CMSIS_DSP build (needs the vendored CMSIS-DSP lib).
int band_energies_naive(const float *x, int n, float fs,
                        float *bands, int n_bands);
#ifdef USE_CMSIS_DSP
int band_energies_cmsis(const float *x, int n, float fs,
                        float *bands, int n_bands);
#endif

#ifdef __cplusplus
}
#endif
