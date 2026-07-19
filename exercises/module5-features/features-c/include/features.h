// Module 5 Track B — feature extraction API
// Conventions are locked to the Python side (notebooks/01+02, validate_features.py):
//   * std  = POPULATION standard deviation (divide by N, like numpy.std default)
//   * zero crossings = count of i in [1, N-1] where (x[i]-mean)*(x[i-1]-mean) < 0
//   * band energies  = Hann-windowed real FFT, |X[k]|^2 summed into n_bands equal
//                      bands over [0, fs/2); DC bin (k=0) and Nyquist bin excluded.
//     Hann: w[i] = 0.5 - 0.5*cos(2*pi*i/(N-1))   (matches numpy.hanning)
// Change a convention on one side only and the validation script WILL fail — by design.

#pragma once
#include <stdint.h>

#define FEAT_FFT_N   256   // FFT length; also the golden-window length
#define FEAT_N_BANDS 5     // 5 x 10 Hz bands at fs = 100 Hz

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
int band_energies_compute(const float *x, int n, float fs,
                          float *bands, int n_bands);

#ifdef __cplusplus
}
#endif
