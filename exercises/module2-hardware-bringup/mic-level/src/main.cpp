/*
 * Module 2 / Exercise 3 — PDM microphone bring-up: RMS level meter
 * Board: RAK4631 (WisBlock), RAK18000 mic in the IO SLOT
 *   PDM DATA = WB_IO3, PDM CLK = WB_IO4
 *
 * The nRF52840 PDM peripheral demodulates the 1-bit mic stream in hardware
 * and DMAs finished int16 PCM samples into RAM (EasyDMA). We double-buffer:
 * while the peripheral fills one buffer, the CPU measures the other.
 *
 * Output: an RMS level + bargraph every ~100 ms. Yell at your board.
 */

#include <Arduino.h>
#include <nrfx_pdm.h>

// ---------------------------------------------------------------- config ---
#define PDM_BUFFER_SAMPLES 256 // samples per DMA buffer (16 ms @ 16 kHz)

// Double buffers: the PDM peripheral writes one while we read the other.
static int16_t pdmBuffer[2][PDM_BUFFER_SAMPLES];
static volatile int nextBufferIndex = 0;

// Handshake between the PDM IRQ and loop(): pointer to a freshly filled buffer.
static int16_t *volatile releasedBuffer = nullptr;

// ------------------------------------------------------------ PDM handler ---
// Called from interrupt context by the nrfx PDM driver.
static void pdm_handler(nrfx_pdm_evt_t const *p_evt)
{
  if (p_evt->error != NRFX_PDM_NO_ERROR) {
    return; // overflow — loop() was too slow; sample dropped
  }
  if (p_evt->buffer_requested) {
    // Peripheral wants its next buffer: hand it the other half.
    nrfx_pdm_buffer_set(pdmBuffer[nextBufferIndex], PDM_BUFFER_SAMPLES);
    nextBufferIndex ^= 1;
  }
  if (p_evt->buffer_released != nullptr) {
    releasedBuffer = (int16_t *)p_evt->buffer_released; // full buffer for loop()
  }
}

// ---------------------------------------------------------------- setup ----
void setup()
{
  Serial.begin(115200);
  uint32_t t0 = millis();
  while (!Serial && (millis() - t0) < 5000) delay(10);

  Serial.println("RAK18000 PDM bring-up — RMS level meter");

  pinMode(LED_BLUE, OUTPUT); // error blink below + your clap light (TODO 3)

  // PDM config: CLK = WB_IO4, DIN (DATA) = WB_IO3
  nrfx_pdm_config_t cfg = NRFX_PDM_DEFAULT_CONFIG(WB_IO4 /*CLK*/, WB_IO3 /*DIN*/);

#if defined(PDM_RATIO_RATIO_Ratio80)
  cfg.clock_freq = NRF_PDM_FREQ_1280K; // 1.28 MHz / 80 = 16.000 kHz
  cfg.ratio      = NRF_PDM_RATIO_80;   // VERIFY: .ratio exists in the BSP's nrfx version
#else
  cfg.clock_freq = NRF_PDM_FREQ_1032K; // fixed ratio 64 -> ~16.125 kHz (close enough)
#endif
  cfg.mode   = NRF_PDM_MODE_MONO;
  cfg.edge   = NRF_PDM_EDGE_LEFTRISING;
  cfg.gain_l = 40; // 0..80, 40 = 0 dB-ish default; raise if too quiet

  nrfx_err_t err = nrfx_pdm_init(&cfg, pdm_handler);
  if (err != NRFX_SUCCESS) {
    Serial.println("ERROR: nrfx_pdm_init failed — is the RAK18000 in the IO slot?");
    while (1) { digitalWrite(LED_BLUE, !digitalRead(LED_BLUE)); delay(100); }
  }

  nrfx_pdm_start(); // fires buffer_requested; DMA begins
  Serial.println("Sampling at 16 kHz. Make some noise...");
}

// ----------------------------------------------------------------- loop ----
void loop()
{
  static uint64_t sumSquares = 0;
  static uint32_t sampleCount = 0;

  if (releasedBuffer != nullptr) {
    int16_t *buf = (int16_t *)releasedBuffer;
    releasedBuffer = nullptr;

    for (int i = 0; i < PDM_BUFFER_SAMPLES; i++) {
      sumSquares += (int32_t)buf[i] * buf[i];
    }
    sampleCount += PDM_BUFFER_SAMPLES;
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

    // TODO(student) 1: convert RMS to dBFS: 20*log10(rms / 32768.0).
    //                  Print it. What's the level of silence? Of speech?

    // TODO(student) 2: also track the min/max sample values per report.
    //                  Clap next to the mic — do you clip (+/-32767)?

    // TODO(student) 3: light LED_BLUE when RMS exceeds a threshold you pick.
    //                  You just built a clap-activated light.

    // TODO(student) 4 (bonus): try cfg.gain_l = 60 and re-flash. What changed?
  }
}
