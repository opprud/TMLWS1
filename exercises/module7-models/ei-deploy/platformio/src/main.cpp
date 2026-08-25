#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_LIS3DH.h>
#include <Adafruit_Sensor.h>
#include <fan-condition-monitoring_inferencing.h> // VERIFY: header name = <EI project name>_inferencing.h

Adafruit_LIS3DH lis;

// EI_CLASSIFIER_DSP_INPUT_FRAME_SIZE = window_samples * axes (e.g. 200*3 = 600)
static float window_buf[EI_CLASSIFIER_DSP_INPUT_FRAME_SIZE];

void setup()
{
    // WisBlock ritual: power the sensor-slot 3V3_S rail — without this the
    // LIS3DH is not on the I2C bus at all. Do not delete.
    pinMode(WB_IO2, OUTPUT);
    digitalWrite(WB_IO2, HIGH);
    delay(100);

    Serial.begin(115200);
    while (!Serial && millis() < 5000)
    {
    }
    if (!lis.begin(0x18))
    {
        Serial.println("LIS3DH not found");
        while (1)
            delay(100);
    }
    lis.setRange(LIS3DH_RANGE_4_G);
    lis.setDataRate(LIS3DH_DATARATE_100_HZ);
    Serial.println("EI fan classifier ready");
}

void loop()
{
    // --- fill one window at the impulse's expected interval -----------------
    for (size_t i = 0; i < EI_CLASSIFIER_RAW_SAMPLE_COUNT; i++)
    {
        uint32_t t0 = micros();
        sensors_event_t ev;
        lis.getEvent(&ev);
        window_buf[i * 3 + 0] = ev.acceleration.x;
        window_buf[i * 3 + 1] = ev.acceleration.y;
        window_buf[i * 3 + 2] = ev.acceleration.z;
        while (micros() - t0 < EI_CLASSIFIER_INTERVAL_MS * 1000)
        {
        } // simple pacing
    }

    // --- wrap the buffer in a signal_t and classify --------------------------
    signal_t signal;
    numpy::signal_from_buffer(window_buf, EI_CLASSIFIER_DSP_INPUT_FRAME_SIZE, &signal);

    ei_impulse_result_t result;
    uint32_t t0 = micros();
    EI_IMPULSE_ERROR err = run_classifier(&signal, &result, false);
    uint32_t dt = micros() - t0;
    if (err != EI_IMPULSE_OK)
    {
        Serial.printf("run_classifier failed (%d)\n", err);
        return;
    }

    // --- report --------------------------------------------------------------
    float best = 0;
    const char *best_label = "?";
    for (size_t i = 0; i < EI_CLASSIFIER_LABEL_COUNT; i++)
    {
        Serial.printf("  %-10s: %.3f\n", result.classification[i].label,
                      result.classification[i].value);
        if (result.classification[i].value > best)
        {
            best = result.classification[i].value;
            best_label = result.classification[i].label;
        }
    }
    Serial.printf("=> %s (%.2f)  inference %lu us  [dsp %d ms, cls %d ms]\n",
                  best_label, best, (unsigned long)dt,
                  result.timing.dsp, result.timing.classification);
}