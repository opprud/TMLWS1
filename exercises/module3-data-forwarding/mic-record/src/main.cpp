/*
 * Module 3 / Exercise B — Microphone RAM recorder + base64 serial dump
 * Board: RAK4631 (WisBlock), RAK18000 mic in the IO SLOT
 *   PDM DATA = WB_IO3, PDM CLK = WB_IO4
 *
 * Flow:
 *   1. Send 'r' in the serial monitor  -> records RECORD_SECONDS of
 *      16 kHz / 16-bit mono PCM straight into a RAM buffer (EasyDMA).
 *   2. The recording is dumped as base64 between BEGIN/END markers.
 *   3. On the PC: save the monitor output to a file and run
 *         python3 pcm_to_wav.py capture.txt fan_normal.01.wav
 *      then upload with edge-impulse-uploader.
 *
 * RAM budget: 2 s * 16000 Hz * 2 B = 64000 B ≈ 62 kB of the nRF52840's 256 kB.
 * ~5 s is the practical ceiling — try it (TODO 3) and meet the linker.
 */

#include <Arduino.h>
#include <nrfx_pdm.h>

// ---------------------------------------------------------------- config ---
#define SAMPLE_RATE_HZ   16000
#define RECORD_SECONDS   2
#define RECORD_SAMPLES   (SAMPLE_RATE_HZ * RECORD_SECONDS)
#define PDM_CHUNK        256 // samples per DMA transfer

// The big one: the whole recording lives here (~62 kB at 2 s).
static int16_t recordBuffer[RECORD_SAMPLES];
static volatile uint32_t samplesWritten = 0; // filled by the PDM IRQ
static volatile bool recording = false;
static volatile bool recordingDone = false;

// ------------------------------------------------------------ PDM handler ---
// DMA writes directly into recordBuffer, chunk by chunk — no copying.
static void pdm_handler(nrfx_pdm_evt_t const *p_evt)
{
  if (p_evt->error != NRFX_PDM_NO_ERROR) {
    return;
  }
  if (p_evt->buffer_requested) {
    uint32_t remaining = RECORD_SAMPLES - samplesWritten;
    if (recording && remaining > 0) {
      uint16_t n = (remaining < PDM_CHUNK) ? remaining : PDM_CHUNK;
      nrfx_pdm_buffer_set(&recordBuffer[samplesWritten], n);
      samplesWritten += n;
    } else {
      // Buffer full: stop the peripheral, signal loop().
      nrfx_pdm_stop();
      recording = false;
      recordingDone = true;
    }
  }
}

// ------------------------------------------------------------ base64 dump ---
static const char b64chars[] =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

static void dumpBase64(const uint8_t *data, uint32_t len)
{
  char line[80];
  int col = 0;
  for (uint32_t i = 0; i < len; i += 3) {
    uint32_t b = (uint32_t)data[i] << 16;
    if (i + 1 < len) b |= (uint32_t)data[i + 1] << 8;
    if (i + 2 < len) b |= data[i + 2];

    line[col++] = b64chars[(b >> 18) & 0x3F];
    line[col++] = b64chars[(b >> 12) & 0x3F];
    line[col++] = (i + 1 < len) ? b64chars[(b >> 6) & 0x3F] : '=';
    line[col++] = (i + 2 < len) ? b64chars[b & 0x3F] : '=';

    if (col >= 76) { // wrap lines: survives every serial monitor
      line[col] = '\0';
      Serial.println(line);
      col = 0;
    }
  }
  if (col > 0) {
    line[col] = '\0';
    Serial.println(line);
  }
}

// ---------------------------------------------------------------- setup ----
void setup()
{
  Serial.begin(115200);
  while (!Serial) delay(10); // recorder is useless without a PC attached

  pinMode(LED_BLUE, OUTPUT); // recording indicator ("blue LED on = recording")

  Serial.println("PDM RAM recorder — 16 kHz mono, 16-bit");
  Serial.print("Buffer: ");
  Serial.print(RECORD_SECONDS);
  Serial.print(" s = ");
  Serial.print(sizeof(recordBuffer) / 1024);
  Serial.println(" kB RAM");

  nrfx_pdm_config_t cfg = NRFX_PDM_DEFAULT_CONFIG(WB_IO4 /*CLK*/, WB_IO3 /*DIN*/);
#if defined(PDM_RATIO_RATIO_Ratio80)
  cfg.clock_freq = NRF_PDM_FREQ_1280K; // /80 -> 16.000 kHz
  cfg.ratio      = NRF_PDM_RATIO_80;   // VERIFY: .ratio exists in the BSP's nrfx version
#else
  cfg.clock_freq = NRF_PDM_FREQ_1032K; // /64 -> ~16.125 kHz; pass --rate 16125 to pcm_to_wav.py
#endif
  cfg.mode   = NRF_PDM_MODE_MONO;
  cfg.edge   = NRF_PDM_EDGE_LEFTRISING;
  cfg.gain_l = 40;

  if (nrfx_pdm_init(&cfg, pdm_handler) != NRFX_SUCCESS) {
    Serial.println("ERROR: nrfx_pdm_init failed — RAK18000 in the IO slot?");
    while (1) { digitalWrite(LED_BLUE, !digitalRead(LED_BLUE)); delay(100); }
  }

  Serial.println("Send 'r' to record.");
}

// ----------------------------------------------------------------- loop ----
void loop()
{
  if (Serial.available() && Serial.read() == 'r' && !recording) {
    samplesWritten = 0;
    recordingDone = false;
    recording = true;
    digitalWrite(LED_BLUE, HIGH);
    Serial.println("Recording...");
    nrfx_pdm_start();
  }

  if (recordingDone) {
    recordingDone = false;
    digitalWrite(LED_BLUE, LOW);

    Serial.print("-----BEGIN AUDIO base64 rate=");
    Serial.print(SAMPLE_RATE_HZ);
    Serial.print(" bits=16 samples=");
    Serial.print(RECORD_SAMPLES);
    Serial.println("-----");
    dumpBase64((const uint8_t *)recordBuffer, sizeof(recordBuffer));
    Serial.println("-----END AUDIO-----");
    Serial.println("Send 'r' to record again.");

    // TODO(student) 1: the first ~50 ms of each recording contains the PDM
    //                  filter's start-up transient (a soft "thump"). Discard
    //                  the first 800 samples before dumping.

    // TODO(student) 2: how long does the dump itself take at 115200 baud?
    //                  Predict it (base64 = 4/3 overhead), then measure with
    //                  millis(). Why is this fine anyway?

    // TODO(student) 3: raise RECORD_SECONDS until the build stops fitting.
    //                  Read the linker error. What is the actual ceiling, and
    //                  which other users of RAM did you just meet?
  }
}
