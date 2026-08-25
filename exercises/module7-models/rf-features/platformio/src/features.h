// Module 7.1 - Feature extraction in C.
// MUST stay in sync with train_rf.py (same formulas, same order):
//   [0..2]  std   x,y,z
//   [3..5]  MAD   x,y,z   (mean absolute deviation around the mean)
//   [6..8]  kurt  x,y,z   (Fisher excess kurtosis, *biased* estimator)
//   [9..11] RMS   x,y,z
//   [12]    mean resultant magnitude sqrt(x^2+y^2+z^2)
//
// Validated Python-vs-C on golden windows (Module 5 methodology).
#pragma once

#include <math.h>
#include <stdint.h>
#include <stddef.h>

#define N_FEATURES 13

static float feat_mean(const float *v, int n, int stride) {
    float s = 0.0f;
    for (int i = 0; i < n; i++) s += v[i * stride];
    return s / (float)n;
}

// Computes std, mad, kurtosis, rms for one axis in a single pass structure.
// v points at the first sample of the axis; stride = 3 (interleaved x,y,z).
static void feat_axis_stats(const float *v, int n, int stride,
                            float *std_out, float *mad_out,
                            float *kurt_out, float *rms_out) {
    const float m = feat_mean(v, n, stride);
    float m2 = 0.0f, m4 = 0.0f, mad = 0.0f, sq = 0.0f;
    for (int i = 0; i < n; i++) {
        const float x = v[i * stride];
        const float d = x - m;
        const float d2 = d * d;
        m2 += d2;
        m4 += d2 * d2;
        mad += fabsf(d);
        sq += x * x;
    }
    m2 /= (float)n;
    m4 /= (float)n;
    *std_out = sqrtf(m2);
    *mad_out = mad / (float)n;
    *kurt_out = (m2 > 0.0f) ? (m4 / (m2 * m2) - 3.0f) : 0.0f;  // biased Fisher
    *rms_out = sqrtf(sq / (float)n);
}

// buf: interleaved samples [x0,y0,z0, x1,y1,z1, ...], n = number of samples.
// out: N_FEATURES floats.
static void calculate_features(const float *buf, int n, float *out) {
    float stdv[3], mad[3], kurt[3], rms[3];
    for (int ax = 0; ax < 3; ax++) {
        feat_axis_stats(buf + ax, n, 3, &stdv[ax], &mad[ax], &kurt[ax], &rms[ax]);
    }
    float res = 0.0f;
    for (int i = 0; i < n; i++) {
        const float x = buf[3 * i], y = buf[3 * i + 1], z = buf[3 * i + 2];
        res += sqrtf(x * x + y * y + z * z);
    }
    res /= (float)n;

    out[0] = stdv[0]; out[1] = stdv[1]; out[2] = stdv[2];
    out[3] = mad[0];  out[4] = mad[1];  out[5] = mad[2];
    out[6] = kurt[0]; out[7] = kurt[1]; out[8] = kurt[2];
    out[9] = rms[0];  out[10] = rms[1]; out[11] = rms[2];
    out[12] = res;
}

// Quantise the float features to the int16 domain the model was trained in.
//
// emlearn's tree runtime is fixed-point: the split thresholds live in an
// int16_t field and inference is integer compares only — no FPU needed. The
// model therefore expects INTEGERS in the units train_rf.py trained on, and
// `scale` must be the array generated alongside the model (feature_scale.h).
// Get this wrong and nothing crashes: every decision boundary just moves, and
// the board reports plausible-looking nonsense.
//
// MUST match quantise() in train_rf.py bit-for-bit:
//   clamp, then round HALF AWAY FROM ZERO (not C's truncating cast, and not
//   numpy's default round-half-to-even).
static void quantise_features(const float *f, const float *scale, int16_t *q) {
    for (int i = 0; i < N_FEATURES; i++) {
        float v = f[i] * scale[i];
        if (v > 32767.0f) v = 32767.0f;
        if (v < -32768.0f) v = -32768.0f;
        q[i] = (int16_t)(v >= 0.0f ? (v + 0.5f) : (v - 0.5f));
    }
}
