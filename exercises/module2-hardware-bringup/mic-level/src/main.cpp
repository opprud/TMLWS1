/*
 * Module 2 / Exercise 3 — PDM microphone bring-up: RMS level meter
 * Board: RAK4631 (WisBlock), RAK18000 mic in the IO SLOT
 *   PDM DATA = WB_IO3, PDM CLK = WB_IO4
 *
 * The nRF52840 PDM peripheral demodulates the 1-bit mic stream in hardware
 * and DMAs finished int16 PCM samples into RAM (EasyDMA). The Adafruit BSP
 * ships an Arduino-style `PDM` library that double-buffers for us: the
 * peripheral fills one half while we read the other.
 *
 * NOTE: the Adafruit nRF52 BSP does NOT ship the raw nrfx PDM *driver*
 * (nrfx_pdm.c is absent — only the header is there), so nrfx_pdm_init()/
 * nrfx_pdm_start() would fail to link, and NRFX_PDM_DEFAULT_CONFIG references
 * an undefined NRFX_PDM_DEFAULT_CONFIG_IRQ_PRIORITY (PDM is not enabled in the
 * BSP's nrfx_config.h). We use the supported `PDM` Arduino library instead.
 *
 * Output: an RMS level + bargraph every ~100 ms. Yell at your board.
  * @note RAK4631 GPIO mapping to nRF52840 GPIO ports
   RAK4631    <->  nRF52840
   WB_IO1     <->  P0.17 (GPIO 17)
   WB_IO2     <->  P1.02 (GPIO 34)
   WB_IO3     <->  P0.21 (GPIO 21)
   WB_IO4     <->  P0.04 (GPIO 4)
   WB_IO5     <->  P0.09 (GPIO 9)
   WB_IO6     <->  P0.10 (GPIO 10)
   WB_SW1     <->  P0.01 (GPIO 1)
   WB_A0      <->  P0.05/AIN3 (AnalogIn A3)
   WB_A1      <->  P0.31/AIN7 (AnalogIn A7)
 */

#include <Arduino.h>
#include <PDM.h>
#include <math.h>

// ---------------------------------------------------------------- config ---
#define PDM_BUFFER_BYTES 512 // 256 int16 samples per half-buffer (16 ms @ 16 kHz)

// Landing zone for one drained buffer. The PDM IRQ fills the library's own
// double buffer; onPDMdata() copies the finished half here for loop() to chew.
static int16_t sampleBuffer[PDM_BUFFER_BYTES / sizeof(int16_t)];
static volatile int samplesRead = 0; // >0 => a fresh block is waiting for loop()

// ------------------------------------------------------------ PDM handler ---
// Called from interrupt context by the PDM library when a buffer fills.
static void onPDMdata()
{
  int bytesAvailable = PDM.available();
  PDM.read(sampleBuffer, bytesAvailable);
  samplesRead = bytesAvailable / sizeof(int16_t);
}

// ---------------------------------------------------------------- setup ----
void setup()
{
  Serial.begin(115200);
  uint32_t t0 = millis();
  while (!Serial && (millis() - t0) < 5000) delay(10);

  Serial.println("RAK18000 PDM bring-up — RMS level meter");

  pinMode(LED_BLUE, OUTPUT); // error blink below + your clap light (TODO 3)

  // PDM pins: DATA (DIN) = WB_IO3, CLK = WB_IO4. Third arg is a mic power-gate
  // pin; the RAK18000 is always powered from the IO slot, so pass -1 (none).
  PDM.setPins(WB_IO3 /*data*/, WB_IO4 /*clk*/, -1 /*pwr*/);
  PDM.setBufferSize(PDM_BUFFER_BYTES);

  // Register the drain callback BEFORE begin() so no block is missed.
  PDM.onReceive(onPDMdata);

  // 1 channel (mono), 16 kHz. begin() resets the gain to its default, so any
  // setGain() must come AFTER begin(). Returns 0 on failure.
  if (!PDM.begin(1 /*mono*/, 16000)) {
    Serial.println("ERROR: PDM.begin failed — is the RAK18000 in the IO slot?");
    while (1) { digitalWrite(LED_BLUE, !digitalRead(LED_BLUE)); delay(100); }
  }

  PDM.setGain(40); // 0..80, 40 = 0 dB-ish default; raise if too quiet
  //PDM.setGain(60); // 0..80, 40 = 0 dB-ish default; raise if too quiet

  Serial.println("Sampling at 16 kHz. Make some noise...");
}

// ----------------------------------------------------------------- loop ----
void loop()
{
  static uint64_t sumSquares = 0;
  static uint32_t sampleCount = 0;
  static int16_t min, max;

  if (samplesRead > 0) {
    int n = samplesRead;
    samplesRead = 0; // release the landing zone for the next IRQ
    min=max=0;

    for (int i = 0; i < n; i++) {
      sumSquares += (int32_t)sampleBuffer[i] * sampleBuffer[i];
      //get min /max
      if(sampleBuffer[i] < min) min = sampleBuffer[i];
      if(sampleBuffer[i] > max) max = sampleBuffer[i];
    }
    sampleCount += n;
  }

  // Every ~100 ms of audio (1600 samples), report RMS + bargraph
  if (sampleCount >= 1600) {
    float rms = sqrtf((float)(sumSquares / sampleCount));
    sumSquares = 0;
    sampleCount = 0;

    int bars = (int)(rms / 100.0f); // crude scale: 100 RMS counts per '#'
    if (bars > 60) bars = 60;
    Serial.print("RMS ");
    Serial.print((int)rms);
    Serial.print("  ");
    for (int i = 0; i < bars; i++) Serial.print('#');
    Serial.println();

#if 0
    // TODO(student) 1: convert RMS to dBFS: 20*log10(rms / 32768.0).
    //                  Print it. What's the level of silence? Of speech?
    float dbfs = 20.0f * log10f(rms / 32768.0f);
    Serial.print("Audio level : ");
    Serial.print(dbfs, 2);
    Serial.println("[dBFS]");

    // TODO(student) 2: also track the min/max sample values per report.
    //                  Clap next to the mic — do you clip (+/-32767)?
    Serial.print("Min sample: ");
    Serial.print(min);
    Serial.print("  Max sample: ");
    Serial.println(max);

    // TODO(student) 3: light LED_BLUE when RMS exceeds a threshold you pick.
    //                  You just built a clap-activated light.
    if(rms > 1000) {
      digitalWrite(LED_BLUE, HIGH);
    } else {
      digitalWrite(LED_BLUE, LOW);
    }

    // TODO(student) 4 (bonus): try PDM.setGain(60) and re-flash. What changed?
#endif
  }
}
