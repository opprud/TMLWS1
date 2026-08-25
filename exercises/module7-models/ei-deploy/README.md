# Exercise 7.2 / 7.3 — Edge Impulse models on the RAK4631

Design an impulse in Edge Impulse Studio (dense NN on spectral features — Exercise 7.2), deploy it as a C++ library, and run it inside your own PlatformIO firmware with a live LIS3DH window. Then repeat with a 1D-CNN on raw windows (Exercise 7.3) and compare.

There is no official EI firmware for the RAK4631 — and that's fine: the C++ deployment path works on **any** board you can compile for. You built the data path yourself in Module 3; now you close the loop.

## Part A — Impulse design (Studio)

1. Open your Module 4 fan project at [studio.edgeimpulse.com](https://studio.edgeimpulse.com). Check **Data acquisition**: every class has train *and* test data (aim ≥ 80/20).
2. **Create impulse** (dense-NN variant):
   - *Time series data*: window size **2000 ms**, window increase **500 ms**, frequency **250 Hz** — these must match your Module 4 acquisition settings exactly (2000 ms at 250 Hz = 500 samples/axis)
   - Processing block: **Spectral Analysis** (all 3 axes)
   - Learning block: **Classification (Keras)**
3. **Spectral features** tab: keep defaults first (low-pass filter, FFT length 64). Click *Save parameters* → *Generate features*. Inspect the **feature explorer** — your five classes should form visible clusters (Module 5 déjà vu: these are RMS + frequency-band features).
4. **NN Classifier** tab: default 2 dense layers (20, 10 neurons) is plenty. Train ~30 cycles, learning rate 0.0005.
   - Expected: validation accuracy ≥ 90 % on a decent dataset. If not: more/cleaner data beats more neurons.
5. **Model testing**: run the held-out test set. Note the accuracy for the worksheet.
6. **Live classification**: stream a window from the device (data forwarder, Module 3) and sanity-check a couple of states before deploying.

## Part B — Deploy as a library

1. **Deployment** page → search **Arduino library** → keep *Unoptimized (float32)* for now (int8 is Module 9) → **Build**, download the zip.
   - The *Arduino library* export is the most PlatformIO-friendly packaging of the C++ SDK — PlatformIO consumes Arduino-format libraries from `lib/` directly. (The plain *C++ library* export works too, but needs manual build-script wiring.)
2. Open the skeleton project in **`platformio/`** (`platformio.ini` and `src/main.cpp` are already there — steps 3 and 4 below are what they contain, for reference) and unzip your export into `lib/`. The SDK itself is *not* in the repo: it is ~23 MB of generated code carrying your model, so everyone unzips their own.

   ```
   fan-ei/
   ├── lib/
   │   └── Fan_Monitor_inferencing/        ← the unzipped export (name = your EI project)
   │       ├── library.properties
   │       └── src/
   │           ├── Fan_Monitor_inferencing.h
   │           ├── edge-impulse-sdk/ ...
   │           ├── model-parameters/ ...
   │           └── tflite-model/ ...
   ├── src/main.cpp
   └── platformio.ini
   ```

3. `platformio.ini`:

   ```ini
   [env:wiscore_rak4631]
   platform = nordicnrf52
   board = wiscore_rak4631
   framework = arduino
   monitor_speed = 115200
   lib_deps =
       adafruit/Adafruit LIS3DH@^1.3.0
       adafruit/Adafruit Unified Sensor@^1.1.14
   build_flags =
       ; use CMSIS-NN kernels on Cortex-M
       -DEI_CLASSIFIER_TFLITE_ENABLE_CMSIS_NN=1
   ```

   <!-- VERIFY: CMSIS-NN flag — recent EI SDKs enable this automatically for Cortex-M targets; harmless if redundant. -->

## Part C — `main.cpp`: wrap the window in a `signal_t`

```cpp
#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_LIS3DH.h>
#include <Adafruit_Sensor.h>
#include <Fan_Monitor_inferencing.h>   // VERIFY: header name = <EI project name>_inferencing.h

Adafruit_LIS3DH lis;

// EI_CLASSIFIER_DSP_INPUT_FRAME_SIZE = window_samples * axes (e.g. 200*3 = 600)
static float window_buf[EI_CLASSIFIER_DSP_INPUT_FRAME_SIZE];

void setup() {
    // WisBlock ritual: power the sensor-slot 3V3_S rail — without this the
    // LIS3DH is not on the I2C bus at all. Do not delete.
    pinMode(WB_IO2, OUTPUT);
    digitalWrite(WB_IO2, HIGH);
    delay(100);

    Serial.begin(115200);
    while (!Serial && millis() < 5000) {}
    if (!lis.begin(0x18)) { Serial.println("LIS3DH not found"); while (1) delay(100); }
    lis.setRange(LIS3DH_RANGE_4_G);
    lis.setDataRate(LIS3DH_DATARATE_100_HZ);
    Serial.println("EI fan classifier ready");
}

void loop() {
    // --- fill one window at the impulse's expected interval -----------------
    for (size_t i = 0; i < EI_CLASSIFIER_RAW_SAMPLE_COUNT; i++) {
        uint32_t t0 = micros();
        sensors_event_t ev;
        lis.getEvent(&ev);
        window_buf[i * 3 + 0] = ev.acceleration.x;
        window_buf[i * 3 + 1] = ev.acceleration.y;
        window_buf[i * 3 + 2] = ev.acceleration.z;
        while (micros() - t0 < EI_CLASSIFIER_INTERVAL_MS * 1000) {} // simple pacing
    }

    // --- wrap the buffer in a signal_t and classify --------------------------
    signal_t signal;
    numpy::signal_from_buffer(window_buf, EI_CLASSIFIER_DSP_INPUT_FRAME_SIZE, &signal);

    ei_impulse_result_t result;
    uint32_t t0 = micros();
    EI_IMPULSE_ERROR err = run_classifier(&signal, &result, false);
    uint32_t dt = micros() - t0;
    if (err != EI_IMPULSE_OK) { Serial.printf("run_classifier failed (%d)\n", err); return; }

    // --- report --------------------------------------------------------------
    float best = 0; const char *best_label = "?";
    for (size_t i = 0; i < EI_CLASSIFIER_LABEL_COUNT; i++) {
        Serial.printf("  %-10s: %.3f\n", result.classification[i].label,
                      result.classification[i].value);
        if (result.classification[i].value > best) {
            best = result.classification[i].value;
            best_label = result.classification[i].label;
        }
    }
    Serial.printf("=> %s (%.2f)  inference %lu us  [dsp %d ms, cls %d ms]\n",
                  best_label, best, (unsigned long)dt,
                  result.timing.dsp, result.timing.classification);
}
```

Notes:

- `signal_from_buffer` builds the `signal_t` callback over your float buffer — no copy, the SDK pulls pages of samples through `signal.get_data`.
- `result.timing.dsp` / `.classification` give you the split for the worksheet; `micros()` around `run_classifier` is the ground truth.
- Blocking sampling (above) is fine for the lab. Bonus: port the ring-buffer/50 %-overlap scheme from `../rf-features/platformio/src/main.cpp` for gapless predictions.

## Part D — Expected output

```
  blocked   : 0.021
  imbalance : 0.903
  normal    : 0.052
  off       : 0.001
  scrape    : 0.023
=> imbalance (0.90)  inference 141253 us  [dsp 129 ms, cls 11 ms]
```

Record: accuracy (Studio *Model testing*), flash/RAM (build summary delta), latency (serial) → worksheet.

## Part E — Exercise 7.3: the CNN variant

1. In Studio, **Create impulse** again (or clone the project): same window, but processing block **Raw data** and learning block **Classification** with a 1D-conv architecture (*expert mode* shows the Keras: `Conv1D → MaxPool → Conv1D → MaxPool → Flatten → Dense`). Start small: 8 + 16 filters, kernel 3 — the old-course grid search showed small CNNs beat big ones on this data size.
2. Train, test, deploy the Arduino library again (bump the version so the folder name differs, or replace the `lib/` folder).
3. Same `main.cpp` — the metadata header re-generates the buffer sizes. Rebuild, measure, fill the CNN worksheet row.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Build explodes with thousands of errors in `edge-impulse-sdk/` | Zip not unpacked at `lib/<Name>/` with `library.properties` at its top level. Don't nest an extra folder. |
| `LIS3DH not found` on serial | The WisBlock sensor slots are power-gated by `WB_IO2` — `setup()` must drive it HIGH before `lis.begin()` (see the Part C template). Also check the RAK1904 sits in sensor slot A (address `0x18`). |
| `region RAM overflowed` at link | Model too big for 256 KB alongside the BSP. Reduce NN size in Studio, or wait for Module 9 (int8). |
| Flash almost full | Normal for CNN + SDK; note it in the worksheet. EON/int8 in Module 9 shrinks it. |
| `run_classifier` returns `-5` / DSP error | Window buffer size ≠ `EI_CLASSIFIER_DSP_INPUT_FRAME_SIZE`; check the impulse frequency matches your sampling loop. |
| Classifications look random live but Studio live-test is fine | Units mismatch: Studio data was recorded in m/s² via the forwarder; make sure firmware feeds m/s² too (Adafruit `getEvent` does). Also check axis order x,y,z. |
| Compile error `printf` float formatting | Adafruit nRF52 core supports `%f` in `Serial.printf`; if not, print with `Serial.print(value, 3)`. <!-- VERIFY --> |
