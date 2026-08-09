/*
 * Module 3 / Exercise B — Microphone RAM recorder + base64 serial dump
 * Board: RAK4631 (WisBlock), RAK18000 mic in the IO SLOT
 *   PDM DATA = WB_IO3, PDM CLK = WB_IO4
 *
 * Flow:
 *   1. Send 'r' in the serial monitor  -> records RECORD_SECONDS of
 *      16 kHz / 16-bit mono PCM straight into a RAM buffer.
 *   2. The recording is dumped as base64 between BEGIN/END markers.
 *   3. On the PC: save the monitor output to a file and run
 *         python3 pcm_to_wav.py capture.txt fan_normal.01.wav
 *      then upload with edge-impulse-uploader.
 *
 * We use the Adafruit BSP's bundled `PDM` Arduino library (<PDM.h>). Its 16 kHz
 * mode runs the peripheral at ratio 80 -> exactly 16.000 kHz. The library owns
 * a small double buffer and hands us finished chunks in the onReceive callback;
 * we copy each chunk into the big recordBuffer until it is full.
 * (The raw nrfx PDM driver, nrfx_pdm.c, is NOT shipped by this BSP — only its
 * header — so nrfx_pdm_init()/NRFX_PDM_DEFAULT_CONFIG do not build/link.)
 *
 * RAM budget: 2 s * 16000 Hz * 2 B = 64000 B ≈ 62 kB of the nRF52840's 256 kB.
 * ~5 s is the practical ceiling — try it (TODO 3) and meet the linker.
 */

#include <Arduino.h>
#include <PDM.h>

// ---------------------------------------------------------------- config ---
#define SAMPLE_RATE_HZ   16000
#define RECORD_SECONDS   2 
#define RECORD_SAMPLES   (SAMPLE_RATE_HZ * RECORD_SECONDS)
#define PDM_CHUNK_BYTES  512 // library double-buffer half: 256 samples per drain

// The big one: the whole recording lives here (~62 kB at 2 s).
static int16_t recordBuffer[RECORD_SAMPLES];
static volatile uint32_t samplesWritten = 0; // filled by the PDM callback
static volatile bool recording = false;
static volatile bool recordingDone = false;

// ------------------------------------------------------------ PDM handler ---
// Called from interrupt context when the library has a fresh chunk. We drain it
// straight into recordBuffer until the recording is full, then flag loop().
static void onPDMdata()
{
  if (!recording) return;

  uint32_t remaining = RECORD_SAMPLES - samplesWritten;
  uint32_t avail = (uint32_t)PDM.available() / sizeof(int16_t);
  uint32_t n = (avail < remaining) ? avail : remaining;

  PDM.read(&recordBuffer[samplesWritten], n * sizeof(int16_t));
  samplesWritten += n;

  if (samplesWritten >= RECORD_SAMPLES) {
    recording = false;
    recordingDone = true; // loop() stops the peripheral (PDM.end) safely
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

  // PDM pins: DATA (DIN) = WB_IO3, CLK = WB_IO4. Third arg is a mic power-gate
  // pin; the RAK18000 is always powered from the IO slot, so pass -1 (none).
  PDM.setPins(WB_IO3 /*data*/, WB_IO4 /*clk*/, -1 /*pwr*/);
  PDM.setBufferSize(PDM_CHUNK_BYTES);
  PDM.onReceive(onPDMdata); // registered once; begin() starts sampling per 'r'

  Serial.println("Send 'r' to record.");
}

// ----------------------------------------------------------------- loop ----
void loop()
{
  if (Serial.available() && Serial.read() == 'r' && !recording && !recordingDone) {
    samplesWritten = 0;
    recording = true;
    digitalWrite(LED_BLUE, HIGH);
    Serial.println("Recording...");
    // begin() resets gain, so setGain() must come after it.
    if (!PDM.begin(1 /*mono*/, SAMPLE_RATE_HZ)) {
      Serial.println("ERROR: PDM.begin failed — RAK18000 in the IO slot?");
      recording = false;
      digitalWrite(LED_BLUE, LOW);
      while (1) { digitalWrite(LED_BLUE, !digitalRead(LED_BLUE)); delay(100); }
    }
    PDM.setGain(40); // 0..80; raise if too quiet
  }

  if (recordingDone) {
    recordingDone = false;
    PDM.end(); // stop the peripheral + free the mic until the next 'r'
    digitalWrite(LED_BLUE, LOW);

    Serial.print("-----BEGIN AUDIO base64 rate=");
    Serial.print(SAMPLE_RATE_HZ);
    Serial.print(" bits=16 samples=");
    Serial.print(RECORD_SAMPLES);
    Serial.println("-----");
    //skip the first 800 samples to avoid the PDM filter's start-up transient
    //(800 samples = 800*2 bytes, so subtract that many BYTES from the length)
    dumpBase64((const uint8_t *)&recordBuffer[800],
               sizeof(recordBuffer) - 800 * sizeof(int16_t));

    //dumpBase64((const uint8_t *)recordBuffer, sizeof(recordBuffer));
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
