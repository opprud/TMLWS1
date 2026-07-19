# Module 3 Lab — Data Acquisition into Edge Impulse

Build the two data pipelines you'll use for the fan lab tomorrow:

| Part | Project | Pipeline | ~Time |
|---|---|---|---|
| 0 | — | create an Edge Impulse project | 10 min |
| A | [`accel-forwarder/`](accel-forwarder/) | LIS3DH → serial CSV → `edge-impulse-data-forwarder` → Studio (live) | 30 min |
| B | [`mic-record/`](mic-record/) | PDM → RAM → base64 dump → `pcm_to_wav.py` → `edge-impulse-uploader` | 30 min |

**Goal:** labelled accelerometer *and* audio data visible in your Edge Impulse project. The data itself is throwaway (gestures, desk noise) — the **pipeline** is the deliverable. Tomorrow it points at the fan.

**Prerequisites:** Module 2 completed; EI account + CLI installed (setup guide §3 — check with `edge-impulse-data-forwarder --version`).

> **Why we build this ourselves:** there is no official Edge Impulse firmware for the RAK4631. The forwarder protocol is just CSV over serial, so writing our own is a feature of this course, not a workaround — afterwards you can connect *any* sensor on *any* board to EI.

---

## Part 0 — Create an Edge Impulse project

1. Log in at [studio.edgeimpulse.com](https://studio.edgeimpulse.com).
2. **Create new project** → name it `tinyml-day1-pipeline` (tomorrow's fan data gets its own project) → Developer plan is fine.
3. Have a look around: **Data acquisition** (empty, for now), **Impulse design**, **Deployment**. We fill these over the next two days.

---

## Part A — Accelerometer → data forwarder

The firmware streams `x,y,z\r\n` CSV lines at a disciplined 100 Hz — the course-wide rate Modules 4–7 train on — paced by an absolute `micros()` deadline, because the forwarder *times your lines* to auto-detect the sample rate, and `delay(10)`-style pacing drifts.

### Steps

1. Open `accel-forwarder/` in VS Code, build, upload.
2. Open the serial monitor **briefly** — you should see a fast stream of CSV triplets. At rest, the third-ish value hovers near ±9.81:

   ```
   0.12,-0.24,9.79
   0.10,-0.19,9.83
   ```

3. **Close the serial monitor.** The forwarder needs the port — one port, one owner. (This is the #1 failure of this lab. You've been warned. Twice, now.)
4. Run the forwarder:

   ```bash
   edge-impulse-data-forwarder
   ```

   - log in with your EI account, select your project
   - it detects the device and reports: **`Detected data frequency: 100Hz`**, 3 axes
   - name the axes: `accX, accY, accZ`
   - give the device a name (e.g. `rak4631-yourname`)

5. In Studio → **Data acquisition**: your device appears under "Record new data". Set:
   - Label: `circle` · Sample length: `5000` ms · Frequency: 100 Hz
6. Click **Start sampling**, and move the board in circles for 5 s. The sample appears in the list — click it and **look at the waveform**. Smooth sinusoids = good.
7. Record ~5 samples each of three gestures: **`circle`**, **`updown`**, **`idle`** (board on the desk).
8. Sanity checks:
   - `idle` samples: flat lines, one axis at ≈9.8
   - `circle` vs `updown`: visibly different waveforms — if *you* can tell them apart by eye, a model can too

### Do the `TODO(student)` items in the firmware

Rate verification, a 50 Hz down-rate experiment (halve `SAMPLE_RATE_HZ`, watch the forwarder re-detect), and the deadline-miss watchdog. Bandwidth context: 100 Hz × ~18 bytes ≈ 1.8 kB/s of the ~11.5 kB/s available at 115200 baud — keep total rate ≤ ~100 Hz × 3 axes, or raise the baud.

---

## Part B — Microphone → WAV → uploader

Raw 16 kHz audio (32 kB/s) doesn't fit through a 115200-baud pipe live — so we record to RAM first, then dump slowly. This is the modern version of the old course's "hex dump + `xxd`" workflow, with the fiddly parts scripted.

### Steps

1. Open `mic-record/`, build, upload, open the monitor (115200). You'll see:

   ```
   PDM RAM recorder — 16 kHz mono, 16-bit
   Buffer: 2 s = 62 kB RAM
   Send 'r' to record.
   ```

2. Start capturing the monitor output to a file. Easiest: CLI monitor with tee —

   ```bash
   pio device monitor | tee capture.txt
   ```

   (Or record in the VS Code monitor and copy-paste everything into `capture.txt` afterwards — markers included.)

3. Type `r` + Enter. Blue LED on = recording (2 s). Speak at the board, or hold a phone tone generator near it (a 1 kHz sine makes a great test signal — you'll recognise it instantly in the waveform).
4. The board dumps base64 between `-----BEGIN AUDIO ...-----` / `-----END AUDIO-----` markers (takes ~8 s — the dump is slower than the recording, and that's fine, nothing is real-time here).
5. Convert to WAV:

   ```bash
   python3 pcm_to_wav.py capture.txt desk_speech.01.wav
   # -> Wrote desk_speech.01.wav: 32000 samples @ 16000 Hz = 2.00 s, 64000 bytes
   ```

6. **Listen to it** (`--play`, or any media player). Intelligible speech, no ticking? Good. Chipmunks or ticking → troubleshooting table.
7. Record a few labelled clips — e.g. `speech`, `silence`, `tone` — one WAV each, named `label.NN.wav`.
8. Upload to your EI project:

   ```bash
   edge-impulse-uploader --category training speech.01.wav silence.01.wav tone.01.wav
   ```

   The uploader takes the label from the filename (everything before the first `.`); use `--label` to override.
9. In Studio → Data acquisition: click an audio sample, look at the waveform, and **play it back in the browser**.

### Do the `TODO(student)` items in the firmware

Start-up transient trimming, dump-time arithmetic, and finding the real RAM ceiling (bring linker-error screenshots for bragging rights).

---

## Finish line checklist

- [ ] Forwarder streams and Studio shows **100 Hz, 3 axes, no gaps**
- [ ] ≥ 5 labelled samples each: `circle`, `updown`, `idle`
- [ ] ≥ 1 audio clip recorded, converted, **listened to**, uploaded with a label
- [ ] You clicked into raw samples in Studio and actually looked at them

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Forwarder: `Failed to get information off device` / no valid readings | **serial monitor still open** — close it; only one program can own the port |
| Forwarder detects wrong frequency (e.g. 92 Hz) | pacing jitter — you replaced the deadline scheduler with `delay()`, didn't you |
| Forwarder connects to the wrong project | `edge-impulse-data-forwarder --clean` to re-select |
| Axis names wrong / want to rename | also `--clean` — names are set at first connect |
| Samples in Studio look chopped / gaps | cable/hub flakiness — use a direct USB port, not a hub |
| `pcm_to_wav.py`: "No BEGIN AUDIO block found" | capture file is missing the marker lines — re-capture including the full dump |
| WAV plays too fast/slow (chipmunk/whale) | clock fallback in use → convert with `--rate 16125` (see the `VERIFY` note in the firmware) |
| WAV has periodic ticks | dropped chunks during dump capture — don't scroll/interact with the monitor mid-dump; prefer `pio device monitor \| tee` |
| Audio is very quiet | raise `cfg.gain_l` (40 → 60) and re-flash |
| Uploader: sample rejected / wrong label | name files `label.NN.wav` or pass `--label`; check the upload summary line |

**Done early?** Start thinking like Day 2: mount the board on something that vibrates (the room's ventilation, your laptop fan exhaust) and record `on` vs `off` accelerometer samples. Can you see the difference in Studio? That's tomorrow's entire morning, in miniature.
