/*
 * Module 2 / Exercise 1 — Blink & serial hello
 * Board: RAK4631 (WisBlock) — nRF52840, Adafruit nRF52 BSP
 *
 * Proves the toolchain: build, flash, serial monitor.
 * The WisBlock core has two LEDs: LED_GREEN and LED_BLUE.
 */

#include <Arduino.h>

static uint32_t blinkCount = 0;

void setup()
{
  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_BLUE, OUTPUT);

  Serial.begin(115200);
  // Wait up to ~5 s for the serial monitor, then carry on regardless.
  // (A hard `while (!Serial);` would hang forever on a bare USB charger.)
  uint32_t t0 = millis();
  while (!Serial && (millis() - t0) < 5000) delay(10);

  Serial.println("RAK4631 alive — hello from PlatformIO!");
}

void loop()
{
  digitalWrite(LED_GREEN, !digitalRead(LED_GREEN));
  Serial.print("blink #");
  Serial.println(++blinkCount);
  delay(500);

  // TODO(student) 1: make LED_BLUE blink alternately with LED_GREEN
  //                  (when green is on, blue is off — and vice versa).

  // TODO(student) 2: change the pattern to a 100 ms double-blink every
  //                  second ("heartbeat"). Keep the serial counter correct.

  // TODO(student) 3: print millis() alongside the counter and check the
  //                  timing in the serial monitor. Is it exactly 500 ms? Why not?
}
