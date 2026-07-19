/*
 * Module 2 / Exercise 2 — Read the RAK1904 accelerometer (LIS3DH)
 * Board: RAK4631 (WisBlock), RAK1904 in SENSOR SLOT A (I2C addr 0x18)
 *
 * Prints x,y,z acceleration in m/s^2 at ~10 Hz (human-readable rate;
 * Module 3 turns this into a disciplined 50 Hz machine-readable stream).
 */

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_LIS3DH.h>
#include <Adafruit_Sensor.h>

#define LIS3DH_I2C_ADDR 0x18 // RAK1904 in sensor slot A

Adafruit_LIS3DH lis = Adafruit_LIS3DH();

void setup()
{
  // --- WisBlock ritual: power the sensor-slot 3V3_S rail. Do not delete. ---
  pinMode(WB_IO2, OUTPUT);
  digitalWrite(WB_IO2, HIGH);
  delay(100); // give the sensor time to boot

  Serial.begin(115200);
  uint32_t t0 = millis();
  while (!Serial && (millis() - t0) < 5000) delay(10);

  Serial.println("RAK1904 / LIS3DH bring-up");

  pinMode(LED_BLUE, OUTPUT); // error blink below + your shake detector (TODO 4)

  if (!lis.begin(LIS3DH_I2C_ADDR)) {
    Serial.println("ERROR: LIS3DH not found at 0x18.");
    Serial.println("Check: module seated? sensor slot A? WB_IO2 HIGH?");
    while (1) { digitalWrite(LED_BLUE, !digitalRead(LED_BLUE)); delay(100); }
  }

  // Vibration-work defaults: +/-4 g range, 50 Hz output data rate.
  lis.setRange(LIS3DH_RANGE_4_G);
  lis.setDataRate(LIS3DH_DATARATE_50_HZ);

  Serial.print("Range: +/-");
  Serial.print(2 << lis.getRange());
  Serial.println(" g. Streaming...");
}

void loop()
{
  sensors_event_t event;
  lis.getEvent(&event); // fills event.acceleration.x/y/z in m/s^2

  Serial.print("X: ");
  Serial.print(event.acceleration.x, 2);
  Serial.print("  Y: ");
  Serial.print(event.acceleration.y, 2);
  Serial.print("  Z: ");
  Serial.print(event.acceleration.z, 2);
  Serial.println(" m/s^2");

  delay(100); // ~10 Hz — readable by humans

  // TODO(student) 1: hold the board still, flat on the table. Which axis
  //                  reads ~9.81? Rotate the board 90 degrees — now which one?

  // TODO(student) 2: compute the magnitude sqrt(x^2+y^2+z^2) and print it.
  //                  What is it at rest, regardless of orientation?

  // TODO(student) 3: change the range to +/-2 g (LIS3DH_RANGE_2_G), shake
  //                  hard, and watch the values clip. Change back to 4 g.

  // TODO(student) 4 (bonus): light LED_BLUE whenever |magnitude - 9.81| > 3
  //                  — congratulations, you built a 1-line shake detector.
}
