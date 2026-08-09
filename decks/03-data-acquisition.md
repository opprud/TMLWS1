---
marp: true
theme: tinyml-clean
paginate: true
---

<!-- _class: title -->

# Module 3
# Data Acquisition

**TinyML — Condition Monitoring on Microcontrollers**
Day 1 · Module 3 of 9

<!--
Final module of Day 1. The hardware works; now we build the pipeline that turns sensor readings into a labelled dataset — because tomorrow morning we record the fan for real, and today is the dress rehearsal on cheap data (wave the board around, talk at it). Two tracks: accelerometer data streamed live into Edge Impulse via the data forwarder, and microphone audio recorded to RAM and uploaded as WAV files. Plus just enough sampling theory to not shoot ourselves in the foot.
-->

---

## The unpopular truth

> **Data quality beats model tuning. Every time.**

- A mediocre model on great data outperforms a great model on garbage
- Most real-world TinyML failures are **dataset failures**:
  wrong sample rate, aliasing, inconsistent mounting, label noise, leakage
- Budget your effort: **80% data, 20% model** is about right

<!--
Set expectations against the industry instinct that the model is the interesting part. In every deployment story worth reading, the wins came from better data, not fancier architectures. The failure list is a preview of this module's checklist: sample rate, aliasing, mounting consistency, labels, leakage. Kaggle-winner wisdom applies doubly on microcontrollers, where the model is too small to paper over data sins.
-->

---

## Sampling: rate

- Sampling = measuring a continuous signal at fixed intervals **fs**
- **Nyquist:** you can only represent frequencies below **fs / 2**
- Everything above fs/2 doesn't disappear — it **folds back** as a lie

| Signal | Bandwidth of interest | Our fs |
|---|---|---|
| Fan vibration | ~20–40 Hz fundamental + harmonics | **50–100 Hz** |
| Fan acoustics | up to ~8 kHz | **16 kHz** |

<!--
Crash course, slide 1 of 2. Nyquist in one sentence: sample at fs, and only content below fs/2 is faithfully captured. Ground it in the fan: a 120 mm fan spins around 1000-2500 RPM depending on model and voltage, so a ~20-40 Hz fundamental — 7 blades put blade-pass around 140-280 Hz. At 100 Hz sampling we get the rotation fundamental (and, for slower fans, its first harmonic) in vibration; the acoustic side at 16 kHz captures everything a fan meaningfully emits. These are the two rates hard-coded in the exercises, now you know where they come from.
-->

---

## Aliasing — the signal that lies

- A 60 Hz vibration sampled at 100 Hz **shows up as 40 Hz**. Plausible. Wrong.
- You cannot detect aliasing after the fact — the data looks *fine*
- Defenses:
  - sample comfortably above 2× the highest *real* frequency
  - know your sensor's bandwidth (LIS3DH internal filtering helps)
  - sanity-check: does the spectrum move as expected when you change the fan speed?

<!--
The horror-story slide. Work the example: 60 Hz real, 100 Hz sampling, Nyquist at 50 — the 60 Hz folds to 40 Hz, indistinguishable from a genuine 40 Hz component. An ML model will happily learn aliased features; they may even "work" until fan speed changes shift the folding and everything breaks silently in production. The practical defense on our rig is the sanity check: change the fan's real speed and verify spectral peaks move the *right* way. If a peak moves the wrong direction as RPM rises, you're staring at an alias. Whiteboard the folding diagram if faces look uncertain.
-->

---

## Windowing

- Models don't eat endless streams — they eat **fixed-size windows**
- Window length = how much context the model sees per decision
  - fan vibration @ 100 Hz: 1–2 s windows → 100–200 samples × 3 axes
  - audio @ 16 kHz: 1 s → 16,000 samples
- **Overlap** (e.g. 50%) = more training windows from the same recording
- Window length is a *hyperparameter you choose at data-collection time*

<!--
Windowing is where continuous reality meets fixed-size model inputs. Guideline: the window must contain several cycles of the phenomenon — at 20-something Hz rotation, one second of vibration holds ~25 revolutions, plenty. Overlap is the free-ish data multiplier: 50% overlap doubles training windows, standard practice (the old WISDM exercise on Day 2 uses exactly 100-sample windows with 50-step overlap). The last bullet is the trap: record too short and you can't use longer windows later. Record generously — you can always cut down.
-->

---

## Range & resolution

- LIS3DH at **±4 g**, 16-bit-ish output → plenty of headroom for fan vibration
- Clipping = information destroyed. Check `describe()` — are your min/max
  pinned at the range limits? Then widen the range.
- Same story for mic gain: too low = noise floor, too high = clipping

**You verified exactly this in the Module 1 pandas exercise.** It's a habit now.

<!--
Callback to the pandas exercise, which was secretly training for this moment: min/max vs sensor range is the first health check on any new recording. Values pinned at ±4g (or audio samples slammed against ±32767) mean clipping — irreversibly destroyed information no amount of modelling repairs. The habit to instill: record 10 seconds, pull it into pandas, describe(), plot, THEN record the real dataset. Thirty seconds of checking saves an afternoon of re-recording — a lesson usually purchased at full price.
-->

---

## Labels & metadata discipline

From the old course's hard-won CSV rules — now enforced by tooling:

- **Name by label:** `circle.1.csv`, `updown.2.csv` → in EI: label per recording
- Record **who/what/when**: which board, which mounting, which fan state
- Keep sessions short and single-label — easier to prune bad data later
- Plan the split **before** recording: train vs test = different sessions

<!--
Labelling discipline, inherited from the old course where students hand-managed CSVs with tee and manual headers — great pedagogy, error-prone practice. Edge Impulse absorbs the bookkeeping (label at record time, metadata fields, train/test buckets) but not the discipline: garbage labels in, garbage model out. Single-label short sessions beat one heroic 10-minute recording because pruning a bad 5-second clip is painless. And the split-by-session rule from module 1 gets its operational form here: record test data as separate sessions, ideally after remounting the sensor.
-->

---

## Edge Impulse — the tour

**Studio** (web): dataset management · labelling · DSP blocks · NN training · live testing · deployment as a C++ library

![w:900](../brightspace-export/_ontent/i39a275e2-29c7-45a0-b627-a4e30b2cc8db/Screenshot%202026-05-14%20at%2010.22.17.png)

<!--
Meet the SaaS backbone of Days 2-3. Edge Impulse Studio: upload or stream data in, label it, design an "impulse" — their word for the DSP-plus-model pipeline — train in the cloud, test live against the device, export a C++ library that compiles into our PlatformIO project. Free for developers. We use it heavily because it collapses a week of glue code into an afternoon; Day 2 module 6 also examines when you'd NOT want it — lock-in, licensing — and what the open alternatives are. Screenshot is from the old course's anomaly lab, UI is current 2026.
-->

---

## Getting data in — our two paths

| Path | Sensor | How |
|---|---|---|
| **Data forwarder** | accelerometer | board prints CSV over serial, CLI streams to Studio |
| **Uploader** | microphone | board dumps PCM → PC converts to WAV → CLI uploads |

⚠️ There is **no official EI firmware for the RAK4631** — and that's fine.
We build our own forwarders. *That is this module.*

<!--
How data reaches Studio. On officially-supported boards EI ships turnkey firmware; the RAK4631 isn't one of them, which we treat as a feature: the forwarder protocol is trivially simple, so we write our own and actually understand our acquisition path — and after this module you can hook ANY sensor on ANY board into EI, which no vendor firmware teaches you. Accelerometer takes the live-streaming path; audio exceeds serial bandwidth for live streaming, so the mic takes the record-then-upload path. Both get built in the lab.
-->

---

## The data forwarder protocol

It's just CSV over serial. Really.

```
0.12,-0.98,9.75\r\n
0.14,-0.95,9.81\r\n
```

- CLI **auto-detects** the rate (by timing lines) and axis count
- Your only job: print values at a **rock-steady rate**
- `edge-impulse-data-forwarder` → login → name axes `accX,accY,accZ` → done

<!--
The whole protocol on one slide: numbers, commas, newline, repeat — at a steady rate. The CLI times your lines to deduce frequency (it will announce "detected 3 axes at 100 Hz") and forwards windows to Studio. Two implications: jittery timing = wrongly detected rate = distorted data, hence the firmware uses a micros()-based scheduler rather than naive delay(10); and the axis names you type at first login stick with the project — use accX/accY/accZ consistently so impulse blocks stay readable.
-->

---

## Serial bandwidth budget

115200 baud ≈ 11,520 bytes/s. A CSV line `"1.23,-4.56,9.81\r\n"` ≈ 18 bytes.

| Stream | Rate | Bytes/s | Verdict |
|---|---|---|---|
| Accel 3-axis CSV | 50 Hz | ~900 | 😌 8% of budget |
| Accel 3-axis CSV | 100 Hz | ~1,800 | 🙂 16% |
| Audio 16 kHz × 16-bit | raw | 32,000 | 💀 3× over budget |

Rule: keep the forwarder ≤ ~100 Hz × 3 axes at 115200 (or raise the baud).

<!--
The arithmetic that dictates our architecture. Walk it: 115200 baud minus framing is ~11.5 KB/s. Fifty-hertz accel CSV uses under a tenth of that — comfortable. Raw 16 kHz audio needs 32 KB/s before we even ASCII-encode it — the pipe is three times too small, full stop. Hence two different pipelines: live streaming for accel, record-to-RAM-then-bulk-dump for audio, where transfer can take longer than the recording because nothing is real-time. This is also why the old course streamed audio over WiFi TCP — the Photon2 had WiFi; our board doesn't, so RAM buffering is the way.
-->

---

## Accel forwarder — firmware architecture

```
LIS3DH @ 100 Hz ──► micros()-scheduled loop ──► Serial.print "x,y,z\r\n"
```

- Pacing by **absolute deadline** (`next += 20000 µs`), not `delay(20)`
  → no drift, no jitter, forwarder detects a clean 100 Hz
- Units: m/s² (multiply g by 9.80665 — EI convention)

<!--
The forwarder firmware in one diagram — it's module 2's accel-read plus a disciplined clock. The scheduling detail matters enough to explain: delay(20) accumulates the loop-body time as drift, and the forwarder's rate autodetect wobbles. Advancing an absolute deadline by exactly 20000 microseconds each cycle self-corrects. That pattern — fixed-rate task on a bare loop — is a generally useful embedded idiom well beyond this course. The m/s² convention comes from EI's accelerometer tooling; the sample code in the old anomaly exercise did the same 9.80665 multiply.
-->

---

## 🧪 Lab checkpoint 1 — accelerometer → Edge Impulse (~30 min)

**`exercises/module3-data-forwarding/accel-forwarder/`**

- Flash the forwarder → **close the serial monitor** → run `edge-impulse-data-forwarder`
- Studio should report **100 Hz, 3 axes**; name them `accX, accY, accZ`
- Record ~5 samples each: `circle`, `updown`, `idle`
- **Done when:** you can *see* the difference between gestures in the raw waveform

<!--
Run this checkpoint before the mic content — the forwarder is the pipeline they reuse tomorrow morning on the fan, so it gets the prime lab slot. The #1 failure is the serial monitor holding the port. While samples record, the mic slides that follow explain what part B will do.
-->

---

## Mic pipeline — record, dump, convert, upload

```
PDM 16 kHz ──► RAM buffer (N s) ──► base64 over serial ──► pcm_to_wav.py ──► edge-impulse-uploader
   (device)        (device)             (slow, fine)           (PC)                (PC)
```

- 2 s × 16 kHz × 2 bytes = **64 KB** — ¼ of total RAM. 5 s ≈ the practical ceiling.
- Base64 = 4/3 overhead but survives serial monitors and copy-paste
- Old course did hex + `xxd` — same idea, ours is scripted

<!--
The audio path, stage by stage. The RAM math from module 2 returns as a real design constraint: 64 KB for two seconds; beyond ~5 seconds the linker starts negotiating with you. Why base64 instead of raw binary: serial monitors mangle binary, base64 is copy-paste-proof and the 33% size tax is irrelevant when the dump isn't real-time. The lineage note: the old course's mic lab dumped hex and reassembled with xxd into WAV — identical concept, we've just wrapped the fiddly part in a Python script that also writes the WAV header. Filename becomes the EI label at upload, so name recordings properly from the start.
-->

---

## Double buffering — the pattern that keeps giving

```
PDM+DMA fills buffer A  ──►  event: A released
        while CPU processes buffer B ──► swap ──► repeat
```

- Zero samples lost; CPU and peripheral never touch the same buffer
- `PDM` library: the double buffer is internal — you drain each finished block in the `onReceive` callback
- Same pattern later carries **live inference** (Day 3): DSP on B while A fills

<!--
The one firmware pattern from this module worth internalising. The PDM peripheral streams continuously and won't wait, so: two buffers, hardware fills one while software drains the other, swap on the event callback. The Adafruit `PDM` library owns the two buffers for us; we just supply an onReceive callback that reads out the finished block. (The raw nrfx PDM driver, which exposes buffer_requested/released directly, is not shipped by this BSP.) Today it feeds a recorder; on Day 3 the identical skeleton runs feature extraction and NN inference on one buffer while the next records — continuous live classification. The old course had a half-finished RAM-buffer assignment gesturing at this; our version actually ships.
-->

---

## 🧪 Lab checkpoint 2 — microphone → WAV → Edge Impulse (~25 min)

**`exercises/module3-data-forwarding/mic-record/`**

- Flash, capture with `pio device monitor | tee capture.txt`, send `r` to record 2 s
- `python3 pcm_to_wav.py capture.txt speech.01.wav` → **listen to it**
- `edge-impulse-uploader --category training speech.01.wav …`
- **Done when:** you've played your clip back in Studio's browser player

<!--
Part B — the slower, RAM-buffered path. The mandatory step is LISTENING to the WAV before uploading: ticks mean dropped dump chunks, chipmunks mean the wrong sample rate (the recorder runs at exactly 16.000 kHz and stamps it in the BEGIN marker, so pcm_to_wav.py picks it up automatically — no --rate needed). One good clip per label beats five unchecked ones.
-->

---

## Edge Impulse Studio — labelling & checking your data

![w:850](../brightspace-export/_ontent/i39a275e2-29c7-45a0-b627-a4e30b2cc8db/Screenshot%202026-05-14%20at%2010.33.38.png)

- Data acquisition tab: every sample, its label, length, train/test bucket
- Click a sample → raw waveform. **Look at your data.** Every time.

<!--
Studio's data-acquisition view, from the old anomaly lab's fresh screenshots. Everything streamed or uploaded lands here with label, duration, and bucket. The habit to preach: click into samples and look at raw waveforms — flat-lined accelerometer channels, clipped audio, a label typo'd as "nromal" — all visible in two seconds here, all invisible once buried in a trained model's confusion matrix. The live-testing views from this same lab return on Day 3 when we do anomaly scoring.
-->

---

## What "good" first data looks like

- Forwarder: Studio shows a steady **100 Hz**, 3 axes, no gaps
- Wave the board in circles → smooth sinusoids; still → flat + gravity on one axis
- Mic: WAV plays back cleanly, speech is intelligible, no ticking (= lost buffers)
- `describe()` sanity: means near 0/0/9.8 m/s² at rest

<!--
Acceptance criteria for the lab — concrete, checkable. The gravity check is the beautiful free diagnostic: a resting accelerometer must read ~9.81 on exactly one axis; anything else means wrong scale factor, wrong range config, or a unit bug. Ticking in the audio playback means dropped buffers — usually the dump-while-recording bug the README warns about. Circles-vs-still is tomorrow's normal-vs-imbalance in miniature: if you can see the difference by eye in the waveform, a model will see it too.
-->

---

## 🧪 Lab finish line — Module 3

Both checkpoints done? Check yourself out:

- [ ] Forwarder streams: Studio shows **100 Hz, 3 axes, no gaps**
- [ ] ≥ 5 labelled samples each: `circle`, `updown`, `idle`
- [ ] ≥ 1 audio clip recorded, converted, **listened to**, uploaded
- [ ] You clicked into raw samples in Studio and actually *looked*

Goal: **both sensor types, labelled, visible in your Studio project.**

<!--
Lab hand-off. The gesture labels are deliberately the old course's gesture-collection exercise reborn — circle, updown, idle are easy to perform repeatably and unmistakable in the waveform, perfect pipeline-validation data. The data itself is disposable; the pipeline is the deliverable, because tomorrow morning the identical flow runs against the fan where re-recording costs real time. Checklist for done: forwarder streaming at detected 100 Hz, at least a few labelled samples of each gesture, one audio clip you've actually listened to, everything visible in Studio. Pairs are fine — one board streams while the other laptop preps the mic track.
-->

---

## Troubleshooting the pipeline

| Symptom | Fix |
|---|---|
| Forwarder: "no valid sensor readings" | close the serial monitor first! One port, one owner |
| Detected rate ≠ 100 Hz | timing jitter — use the deadline scheduler, not `delay()` |
| Forwarder asks to log in every time | `edge-impulse-data-forwarder --clean` re-pick project |
| WAV sounds like a chipmunk | rate mismatch — dump was not 16 kHz, check `--rate` |
| Upload lands unlabeled | `--label` flag or rename file to `label.xx.wav` |

<!--
The pipeline-specific failure table for the projector during the lab. Star of the show: the serial port is exclusive — the PlatformIO monitor and the data forwarder cannot both hold it, and "no sensor readings" nearly always means the monitor is still open. Chipmunk audio = sample-rate mismatch between what the firmware recorded and what the WAV header claims — the --rate flag on the Python script. These map straight to the README troubleshooting boxes.
-->

---

## Day 1 wrap-up

| | Achieved |
|---|---|
| ✅ | ML fundamentals + trained NNs in Keras |
| ✅ | RAK4631 toolchain, accel, mic all alive |
| ✅ | Labelled sensor data flowing into Edge Impulse |

**Tomorrow:** mount the sensor on the fan, define fault states,
record a *disciplined* dataset — then make features of it.

<!--
Day 1 close. The whole chain exists end-to-end: theory, hardware, pipeline, labelled cloud dataset — most TinyML tutorials end where we're starting tomorrow. Homework, optional but smart: skim your streamed data in Studio tonight; and if anyone wants a head start, think about which physical fan faults we can stage — bring ideas. Tomorrow 9:00, the fans come out of the boxes. Bring the kit back assembled, bring the laptop charged.
-->
