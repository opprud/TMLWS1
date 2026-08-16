/*
 * Module 3 / Exercise A — Edge Impulse data forwarder firmware
 * Board: RAK4631 (WisBlock), RAK1904 (LIS3DH) in SENSOR SLOT A (0x18)
 *
 * Streams 3-axis acceleration as CSV lines over USB serial at a rock-steady
 * 250 Hz, in the exact format edge-impulse-data-forwarder expects:
 *
 *     x.xx,y.yy,z.zz\r\n
 *
 * The forwarder auto-detects the rate by timing the lines, so pacing is done
 * with an absolute micros() deadline (no drift) instead of delay() (drifts).
 *
 * 250 Hz is the course-wide convention (Modules 4-7 train on 250 Hz windows).
 * Nyquist is 125 Hz, enough to see the fan's rotation harmonics that 100 Hz
 * would alias. Bandwidth check: 250 Hz * ~18 bytes/line = ~4.5 kB/s of the
 * ~11.5 kB/s that 115200 baud provides — still comfortable for 3 axes.
 */

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_LIS3DH.h>
#include <Adafruit_Sensor.h>

#define LIS3DH_I2C_ADDR   0x18
#define SAMPLE_RATE_HZ    250
#define SAMPLE_PERIOD_US  (1000000UL / SAMPLE_RATE_HZ) // 4000 us

// Edge Impulse convention is m/s^2. NOTE: unused here — Adafruit's getEvent()
// already returns m/s^2. Kept for reference in case you switch to raw reads.
#define CONVERT_G_TO_MS2  9.80665f

Adafruit_LIS3DH lis = Adafruit_LIS3DH();
static uint32_t nextSampleDeadline; // absolute micros() deadline

void setup()
{
  // Power the WisBlock sensor slots (3V3_S rail)
  pinMode(WB_IO2, OUTPUT);
  digitalWrite(WB_IO2, HIGH);
  delay(100);

  Serial.begin(115200);
  uint32_t t0 = millis();
  while (!Serial && (millis() - t0) < 5000) delay(10);

  pinMode(LED_BLUE, OUTPUT);   // error indicator — this sketch prints nothing

  if (!lis.begin(LIS3DH_I2C_ADDR)) {
    // Deliberately NOT printing an error banner in a tight loop here:
    // stray non-CSV lines confuse the data forwarder's autodetection.
    while (1) { digitalWrite(LED_BLUE, !digitalRead(LED_BLUE)); delay(100); }
  }

  lis.setRange(LIS3DH_RANGE_4_G);
  // The LIS3DH has no 250 Hz ODR (native steps: 100, 200, 400 Hz), so run it at
  // 400 Hz — internally faster than our 250 Hz read rate, so getEvent() always
  // returns a fresh sample and the anti-alias filter sits above our Nyquist.
  lis.setDataRate(LIS3DH_DATARATE_400_HZ);

  nextSampleDeadline = micros() + SAMPLE_PERIOD_US;
}

void loop()
{
  // Wait for the deadline (busy-wait is fine — precision beats power today)
  while ((int32_t)(micros() - nextSampleDeadline) < 0) { /* spin */ }
  nextSampleDeadline += SAMPLE_PERIOD_US; // absolute schedule: no drift

  sensors_event_t event;
  lis.getEvent(&event); // m/s^2

  // Exact forwarder format: "x,y,z\r\n"
  Serial.print(event.acceleration.x, 2);
  Serial.print(',');
  Serial.print(event.acceleration.y, 2);
  Serial.print(',');
  Serial.print(event.acceleration.z, 2);
  Serial.print("\r\n");

  // TODO(student) 1: verify the rate. Run `edge-impulse-data-forwarder` —
  //                  it should report "3 axis ... at 250Hz". If it reports
  //                  249 or 251 Hz, something in your loop is stealing time.

  // TODO(student) 2: halve SAMPLE_RATE_HZ to 125 and re-check detection, then
  //                  set it back to 250 — the course-wide convention that
  //                  Modules 4-7 train on. (Keep the LIS3DH ODR >= your
  //                  sample rate — here the ODR is 400 Hz.)

  // TODO(student) 3 (bonus): replace the busy-wait with a check that flags
  //                  (LED_BLUE on) if we ever MISS a deadline — a watchdog
  //                  for jitter. When does it trigger? (Hint: TODO 1.)
}
