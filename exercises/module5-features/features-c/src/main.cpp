// Module 5 Track B — compute features on-device and print them for validation.
//
// Modes (single character over the serial monitor):
//   g  (default, auto-repeats every 5 s)  — features on the deterministic
//        SYNTHETIC golden window. validate_features.py generates the identical
//        window in numpy and compares the numbers.
//   l  — capture a LIVE FEAT_FFT_N-sample window from the RAK1904 (LIS3DH,
//        slot A, I2C 0x18) at FS and print its features.
//
// To use a golden window exported from notebook 02 instead of the synthetic one:
//   1) run notebook 02 section 8 — it writes include/golden/win_<label>.h
//      (and a .csv twin for the Python side) directly into this project.
//   2) #include it below and point GOLDEN_WINDOW / GOLDEN_LEN at the array.

#include <Arduino.h>
#include <Adafruit_LIS3DH.h>
#include <Adafruit_Sensor.h>
#include "features.h"

// ---- configuration ---------------------------------------------------------
// FS must match the Module 4 recordings AND validate_features.py — the script
// reads the fs we print below and aborts on a mismatch (band edges depend on it).
static const float FS = 250.0f;          // Hz — matches Module 4 recordings
static const int N = FEAT_FFT_N;         // 512 samples = 2.048 s @ 250 Hz

// Synthetic golden window — MUST match validate_features.py exactly:
//   x[i] = 0.8*sin(2*pi*25*i/fs) + 0.3*sin(2*pi*40*i/fs) + 0.05*sin(2*pi*3.1*i/fs + 1.0)
static void make_synthetic_window(float *x, int n, float fs)
{
    const float two_pi = 2.0f * (float)M_PI;
    for (int i = 0; i < n; i++) {
        const float t = (float)i / fs;
        x[i] = 0.8f * sinf(two_pi * 25.0f * t)
             + 0.3f * sinf(two_pi * 40.0f * t)
             + 0.05f * sinf(two_pi * 3.1f * t + 1.0f);
    }
}

// Uncomment to run on a window exported from your own fan data
// (notebook 02, section 8 — README A2 step 7). Change all FOUR lines together:
// GOLDEN_NAME is printed over serial so validate_features.py can check you are
// comparing against the matching .csv twin and not some other class.

#if 0
#include "golden/win_normal.h"
#define GOLDEN_NAME   "win_normal"
#define GOLDEN_WINDOW win_normal
#define GOLDEN_LEN    WIN_NORMAL_LEN
#else
#include "golden/win_imbalance.h"
#define GOLDEN_NAME   "win_imbalance"
#define GOLDEN_WINDOW win_imbalance
#define GOLDEN_LEN    WIN_IMBALANCE_LEN
#endif


#ifdef GOLDEN_WINDOW
// Regenerating the goldens with a different FFT_N would silently overrun
// window_buf in the memcpy below — catch it at compile time instead.
static_assert(GOLDEN_LEN == FEAT_FFT_N,
              "golden window length != FEAT_FFT_N — re-export from notebook 02 "
              "section 8 with FFT_N matching features.h");
#endif

// ---- globals ----------------------------------------------------------------
static float window_buf[FEAT_FFT_N];
static Adafruit_LIS3DH lis;
static bool lis_ok = false;
static char linebuf[160];

static void print_features(const char *window_name)
{
    time_features_t tf;
    float bands[FEAT_N_BANDS];

    uint32_t t0 = micros();
    time_features_compute(window_buf, N, &tf);
    uint32_t stats_us = micros() - t0;

#ifdef USE_CMSIS_DSP
    // Run BOTH FFT backends on the same window and time each. `bands` (printed
    // below and validated against numpy) comes from CMSIS; the naive result is
    // only used to time the plain-C DFT and cross-check agreement.
    float bands_naive[FEAT_N_BANDS];
    t0 = micros();
    int rc_naive = band_energies_naive(window_buf, N, FS, bands_naive, FEAT_N_BANDS);
    uint32_t fft_naive_us = micros() - t0;

    t0 = micros();
    int rc = band_energies_cmsis(window_buf, N, FS, bands, FEAT_N_BANDS);
    uint32_t fft_cmsis_us = micros() - t0;

    float agree_max_rel = 0.0f;
    if (rc == 0 && rc_naive == 0) {
        for (int b = 0; b < FEAT_N_BANDS; b++) {
            float denom = fabsf(bands[b]);
            if (denom < 1e-6f) denom = 1e-6f;
            float rel = fabsf(bands[b] - bands_naive[b]) / denom;
            if (rel > agree_max_rel) agree_max_rel = rel;
        }
    }
#else
    t0 = micros();
    int rc = band_energies_compute(window_buf, N, FS, bands, FEAT_N_BANDS);
    uint32_t fft_us = micros() - t0;
#endif

    Serial.println("FEATURES_BEGIN");
#ifdef GOLDEN_NAME
    snprintf(linebuf, sizeof(linebuf), "window=%s golden=%s n=%d fs=%.1f",
             window_name, GOLDEN_NAME, N, (double)FS);
#else
    snprintf(linebuf, sizeof(linebuf), "window=%s n=%d fs=%.1f", window_name, N, (double)FS);
#endif
    Serial.println(linebuf);
    snprintf(linebuf, sizeof(linebuf),
             "axis=x mean=%.6f std=%.6f rms=%.6f min=%.6f max=%.6f zc=%d",
             (double)tf.mean, (double)tf.std, (double)tf.rms,
             (double)tf.min, (double)tf.max, tf.zero_crossings);
    Serial.println(linebuf);
    if (rc == 0) {
        snprintf(linebuf, sizeof(linebuf),
                 "axis=x band0=%.6e band1=%.6e band2=%.6e band3=%.6e band4=%.6e",
                 (double)bands[0], (double)bands[1], (double)bands[2],
                 (double)bands[3], (double)bands[4]);
        Serial.println(linebuf);
    } else {
        Serial.println("axis=x bands=ERROR");
    }
#ifdef USE_CMSIS_DSP
    // fft_us kept as an alias (= CMSIS) so validate_features.py's timing line
    // still resolves; the two explicit numbers are the actual comparison.
    snprintf(linebuf, sizeof(linebuf),
             "timing stats_us=%lu fft_us=%lu fft_naive_us=%lu fft_cmsis_us=%lu",
             (unsigned long)stats_us, (unsigned long)fft_cmsis_us,
             (unsigned long)fft_naive_us, (unsigned long)fft_cmsis_us);
    Serial.println(linebuf);
    snprintf(linebuf, sizeof(linebuf), "fft_agree max_rel=%.2e", (double)agree_max_rel);
    Serial.println(linebuf);
#else
    snprintf(linebuf, sizeof(linebuf), "timing stats_us=%lu fft_us=%lu",
             (unsigned long)stats_us, (unsigned long)fft_us);
    Serial.println(linebuf);
#endif
    Serial.println("FEATURES_END");
}

// Capture N samples of one axis (X) at FS from the LIS3DH.
// Simple polled pacing — good enough for a feature demo; the Module 3
// forwarder firmware shows the timer-driven pattern for production sampling.
static bool capture_live_window(void)
{
    if (!lis_ok) return false;
    const uint32_t period_us = (uint32_t)(1000000.0f / FS);
    uint32_t next = micros();
    for (int i = 0; i < N; i++) {
        while ((int32_t)(micros() - next) < 0) { /* wait */ }
        next += period_us;
        sensors_event_t event;
        lis.getEvent(&event);
        window_buf[i] = event.acceleration.x;   // m/s^2; pick your liveliest axis
    }
    return true;
}

void setup()
{
    // --- WisBlock ritual: power the sensor-slot 3V3_S rail. Do not delete. ---
    pinMode(WB_IO2, OUTPUT);
    digitalWrite(WB_IO2, HIGH);
    delay(100);                               // give the sensor time to boot

    Serial.begin(115200);
    uint32_t t0 = millis();
    while (!Serial && millis() - t0 < 5000) { delay(10); }   // wait max 5 s for monitor

    lis_ok = lis.begin(0x18);                 // RAK1904 in sensor slot A
    if (lis_ok) {
        lis.setRange(LIS3DH_RANGE_4_G);       // +/-4 g, as in Module 4
        // ODR must be ABOVE the polling rate or every poll re-reads the same
        // OUT registers: at 250 Hz polling a 100 Hz ODR gives ~2.5 copies of
        // each sample — a stair-stepped signal that still "validates" (both
        // sides see the same array) but is spectrally wrong. 400 Hz ODR at
        // 250 Hz polling is the Module 3 forwarder convention.
        lis.setDataRate(LIS3DH_DATARATE_400_HZ);
        Serial.println("# LIS3DH ready (0x18, +/-4g, ODR 400 Hz, polled at FS)");
    } else {
        Serial.println("# LIS3DH not found — live mode 'l' disabled, golden mode works");
    }
    Serial.println("# commands: g = golden synthetic window, l = live capture");
}

void loop()
{
    static uint32_t last = 0;
    char cmd = 0;

    if (Serial.available()) cmd = (char)Serial.read();

    if (cmd == 'l') {
        snprintf(linebuf, sizeof(linebuf), "# capturing %d live samples at %.1f Hz...",
                 N, (double)FS);
        Serial.println(linebuf);
        if (capture_live_window()) {
            print_features("live");
        } else {
            Serial.println("# live capture unavailable (no sensor)");
        }
        last = millis();
    } else if (cmd == 'g' || millis() - last > 5000) {
#ifdef GOLDEN_WINDOW
        memcpy(window_buf, GOLDEN_WINDOW, sizeof(float) * N);
        print_features("golden_file");
#else
        make_synthetic_window(window_buf, N, FS);
        print_features("synthetic");
#endif
        last = millis();
    }
}
