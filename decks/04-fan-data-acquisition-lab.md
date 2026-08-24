---
marp: true
theme: tinyml-clean
paginate: true
---

<!-- _class: title -->

# Module 4
# Build a Data-Acquisition System

**The Fan Lab: condition monitoring of a rotating machine**
TinyML Course · Day 2

<!--
Welcome to Day 2. Yesterday you got the toolchain running, brought up the RAK4631 + RAK1904, and streamed your first samples into Edge Impulse. Today we turn that plumbing into an actual condition-monitoring system. This module is 90% lab: by lunch every participant should own a labelled 5-class vibration dataset recorded from their own fan. Emphasise that everything on Day 2 and 3 builds on THIS dataset — sloppy data today means frustrating models tomorrow.
-->

---

# Warm-up — four questions from Day 1

1. Train/test split for sensor data: by **window** or by **recording session** — and why?
2. The fan's **175 Hz** blade-pass, sampled at 250 Hz, shows up at what frequency?
3. The data forwarder reports **160 Hz** instead of 250 Hz. Most likely cause?
4. On the nRF52840, where do a model's **weights** live — RAM or flash?

*Two minutes with your neighbour, then we compare notes.*

<!--
Day-boundary retrieval — cheap and it works. Let pairs argue for two minutes, then collect answers cold. Answers: (1) by recording session — adjacent windows from one recording are near-duplicates, splitting by window leaks them into both sets and the accuracy becomes a lie (Module 1/3). (2) 75 Hz — 175 Hz folds around Nyquist at 125 Hz (250-175), landing mid-band where it is indistinguishable from a real 75 Hz component; aliasing, and you can't detect it after the fact (Module 3). (3) delay()-based loop timing — jitter accumulates; use the absolute-deadline micros() scheduler. A second plausible answer worth accepting at 250 Hz: the LIS3DH ODR is set at or below the polling rate, so the loop stalls on stale registers (Module 3). (4) Flash (1 MB) holds the weights; RAM (256 KB) holds activations and buffers (Module 1, and the full story in Module 9). Anyone shaky on 1 or 3 gets a personal visit during this morning's lab — those two are exactly the mistakes that ruin today's dataset.
-->

---

# Three questions before you touch the hardware

1. **What exactly counts as "failure"** for this machine — and would an expert agree?
2. **Who consumes the alert** — a dashboard, a technician's phone, a maintenance queue?
3. **What does a false alarm cost** vs a missed fault?

![w:560](assets/reddi/3-8-4-false-positive-cost.png)

<sub>Figure: TinyML on edX (HarvardX), V.J. Reddi et al. — used with permission · Question framing after V.J. Reddi</sub>

<!--
Five-minute discussion before anyone picks up a zip-tie — these three questions are the difference between a demo and a product. Q1 decides your label set (we chose five states — was that right?). Q2 decides latency and integration requirements. Q3 decides where you put the threshold on Day 3: a false alarm costs a technician visit; a missed bearing failure costs a warranty claim and an angry customer. There is no universally right answer — but there is always a wrong one: not having decided. Collect one answer per pair, revisit after the anomaly module tomorrow.
-->

---

# Day 2 roadmap

| Module | Topic | Output |
|---|---|---|
| **4 (now)** | Fan lab — record a disciplined dataset | Labelled 5-class dataset in Edge Impulse |
| 5 | Feature engineering (time + frequency domain) | Features in Python **and** C |
| 6 | ML frameworks for MCUs | emlearn XOR running on your RAK4631 |

<!--
One narrative arc: sensor data (M4) becomes features (M5), features become a deployed model (M6, and the full fan model on Day 3). Point at the dependency explicitly — the dataset recorded this morning is reused in modules 5, 7 and 8.
-->

---

# Why condition monitoring?

- Rotating machines (pumps, fans, motors, compressors) **fail in patterns**: imbalance, misalignment, bearing wear, cavitation, blockage
- Classic maintenance strategies:
  - **Run-to-failure** — cheap until it isn't
  - **Scheduled** — replaces healthy parts, misses early failures
  - **Condition-based** — act when the *machine* says so
- Vibration is the richest, cheapest signal for rotating machinery
- TinyML angle: analyse **at the sensor**, transmit only *state*, not raw waveforms

<!--
The audience works with pumps daily — they know them better than we do. Invite one example from the room: "what does a failing pump sound/feel like?" The TinyML value proposition: a LoRa node cannot stream 250 Hz × 3-axis raw data on a battery, but it can happily send "state=imbalance, confidence=0.93" once a minute. Jon Nordby's cattle-collar figure: on-sensor ML uses ~50x less power than streaming raw data (we revisit in Module 6).
-->

---

# Our target machine: a 120 mm PC fan

- Stand-in for a pump: rotor + bearing + airflow + housing
- 5 V/12 V, ~1000–2500 RPM depending on model and voltage
- Rotation fundamental: **RPM/60 ≈ 20–40 Hz** — comfortably inside our accelerometer bandwidth
- Cheap enough to *deliberately break* — try that with a CR pump

![height:280](../brightspace-export/_ontent/i39a275e2-29c7-45a0-b627-a4e30b2cc8db/Screenshot%202026-05-14%20at%2010.22.17.png)

<!-- TODO: image above is the Edge Impulse project screenshot used as placeholder — replace with a photo of the actual fan rig (fan + WisBlock zip-tied to frame) once a rig photo is taken. -->

<!--
Explain the analogy limits honestly: a PC fan has a sleeve/ball bearing and plastic blades, a pump has fluid coupling and cavitation — but the *methodology* (mount sensor, define states, record, extract features, classify) transfers 1:1. Mention the fan RPM number now; it becomes crucial in Module 5 when we look at spectra.
-->

---

# Vibration signatures of rotating machines

| Fault | Typical signature |
|---|---|
| **Imbalance** | Strong sinusoid at 1× rotation frequency, radial |
| **Misalignment** | 2× rotation frequency components |
| **Bearing wear** | Broadband noise + high-frequency bursts |
| **Rub / scrape** | Impulsive, harmonic-rich, often audible |
| **Flow blockage** | Changed load → RPM shift + reduced broadband level |

- Fault physics live in **both** amplitude statistics *and* frequency content
- This is why Module 5 covers time-domain **and** spectral features

<!--
Keep this qualitative — the point is to build intuition for WHY the five states we record next are distinguishable at all. 1x imbalance is the textbook example: a mass on one blade produces a rotating centrifugal force vector, which the accelerometer sees as a sine at the rotation frequency. Scraping produces impacts — rich harmonics, high kurtosis. Blockage changes the aerodynamic load, so RPM shifts up (less air moved = less load on most axial fans) — a frequency feature, invisible to a plain RMS level.
-->

---

# The five machine states

| Label | How to create it | What physics says |
|---|---|---|
| `normal` | Fan running free, nothing attached | Baseline 1× tone + broadband |
| `imbalance` | **Tape a small weight** (2–4 cm tape blob / M3 nut) to ONE blade | Boosted 1× tone |
| `blocked` | Cover intake/exhaust with cardboard (≥ 80 %) | RPM shift, reduced flow noise |
| `scrape` | Zip-tie / paper edge lightly touching blades | Impulsive, high kurtosis |
| `off` | Fan unpowered | Sensor noise floor only |

**Rule: change ONE thing per state.** Same fan, same mounting, same voltage.

<!--
Safety + practicality: the scrape state should be a LIGHT touch — a piece of paper or the tip of a zip-tie flexed against the blade tips. Don't jam anything stiff into the fan. The `off` class matters more than it looks: it teaches the model (and the anomaly detector on Day 3) what "no machine" looks like, and it's the easiest sanity check of the whole pipeline. If your classifier can't tell `off` from `normal`, your wiring is broken, not your model.
-->

---

# Sensor mounting — coupling is everything

- RAK1904 (LIS3DH) sits on the WisBlock base — so we mount **the whole board** on the fan frame
- **Rigid coupling** transmits vibration; soft coupling low-pass filters it away
  - Good: zip-ties pulled tight, double-sided *thin* tape, screw through a mounting hole
  - Bad: blu-tack blobs, foam tape, dangling by the USB cable
- Mount on the **frame corner**, not on the sticker over the motor hub
- Cable strain relief: tape the USB lead to the desk so it can't rattle

<!-- TODO: re-capture: photo of WisBlock zip-tied to a 120 mm fan corner. The old course has no fan rig photo; the closest is a Photon2 breadboard photo (brightspace-export/_ontent/i15ac4701-536e-48d2-940d-a4071acfb016/IMG_9114*.jpeg) which must NOT be reused. -->

<!--
This slide saves more model accuracy than any hyperparameter. A floppy mount attenuates exactly the high-frequency content that distinguishes scrape from imbalance. Demonstrate live: hold the board loosely vs zip-tied while watching the serial plotter. Also mention axis orientation: note which sensor axis points along the fan's rotation axis and write it in the project notes — you'll want it when interpreting spectra in Module 5.
-->

---

# Acquisition parameters

- **Sample rate: 250 Hz** (LIS3DH ODR 400 Hz, ±4 g — ODR must exceed the polling rate)
  - Nyquist = 125 Hz → the 20–40 Hz rotation fundamental **and several harmonics**
  - Blade-pass (blades × RPM/60 ≈ 140–280 Hz) still straddles Nyquist — we knowingly give it up, and it folds back into the band
- **Window length: 2 s** → 500 samples/axis; several rotation periods per window
- **Recording length: 20 s per sample** → EI slices into windows later
- ±4 g range: scraping impacts can exceed ±2 g; clipping destroys data

<!--
Connect back to Module 3's sampling theory. The deliberate trade-off is worth dwelling on: even at 250 Hz we cannot see blade-pass or bearing tones — that is what the RAK18000 microphone track (Day 3 option) is for. Ask: "what would we need to capture blade pass at 280 Hz?" (≥ 560 Hz sampling — the LIS3DH can do up to 5.3 kHz in low-power mode, but the data forwarder over 115200 baud serial becomes the bottleneck: at 250 Hz x 3 axes we already use ~39% of the link, so 560 Hz would need a higher baud rate). Window length rationale: at 25 Hz rotation, 2 s = 50 revolutions — plenty for stable statistics, and 500 samples is still a comfortable buffer on the nRF52840.
-->

---

# 🧪 Lab step 1 — build the rig (~25 min)

**`exercises/module4-fan-dataset/README.md`** → sections 1–2

- Zip-tie the WisBlock to the fan frame — **rigid coupling**, connector clear
- Flash Module 3's forwarder → verify **≈250 Hz** detected
- Fan on `normal`: watch the live waveform — visible periodicity = good coupling
- **Done when:** forwarder streams clean data with the fan running

<!--
Build first, record later — the discipline rules that follow only make sense with a working rig in front of them. Enforce rigid mounting: tape+foam kills exactly the high-frequency content Module 5 needs. Pairs share a rig but everyone must end with the dataset in their own EI project (EI supports collaborators — simpler: one recorder, export/import raw data).
-->

---

# Why dataset discipline beats model tuning

- "Garbage in, garbage out" is not a slogan, it's a budget statement:
  - 1 h spent on clean data ≈ days saved on debugging mystery accuracy
- Typical silent failure: **the model learns your recording session**, not the machine state
  - Different desk, different USB cable tension, different room → different data
- The test set must answer: *"does this work on data the model has never seen?"*
  — not: *"can the model memorise Tuesday morning?"*

<!--
This is the core lecture message of Module 4; everything else is procedure. Concrete horror story to tell: a class of students recorded "normal" in the morning and "fault" after lunch — the model learned the building's HVAC cycle and got 99% accuracy that evaporated the next day. That's leakage via session, and it is why we interleave states during recording (next slides).
-->

---

# Discipline rule 1 — repetitions, interleaved

- Record **≥ 5 separate recordings per state**, 20 s each
  → ≥ 100 s/state, ≥ 50 windows/state at 2 s windows
- **Interleave** states: don't record all `normal` then all `imbalance`
  - Cycle: normal → imbalance → blocked → scrape → off → repeat
- Between repetitions of the *same* state: **remount / restart** something
  - Re-stick the tape weight at a slightly different radius
  - Power-cycle the fan
  - Nudge the zip-tie mount

<!--
Interleaving decorrelates the state label from slow drifts (temperature, desk vibration from neighbours, USB cable position). Varying the tape position between imbalance recordings is deliberate: we want the model to learn "imbalance", not "this exact 3-gram blob at radius 40 mm". This is data augmentation done physically.
-->

---

# Discipline rule 2 — train/test hygiene

- Edge Impulse default: ~80/20 train/test split — **keep it**
- Split by **recording**, never by window
  - Adjacent 2 s windows from one 20 s recording are near-duplicates
  - If windows from the same recording land in both train *and* test → leakage → fake accuracy
- Practical rule in EI: assign whole *samples* (recordings) to Test, e.g. your last recording of each state
- Never look at test data during Module 5's feature exploration

<!--
Edge Impulse splits at the sample (file) level when you use the "perform train/test split" function, which is exactly what we want — one 20 s recording is one file. The WISDM notebook in Module 5 uses split-by-user for the same reason (train users 1–27, test users 28–36). The principle generalises: split along the axis you expect to generalise across. For production fleets: split by pump serial number.
-->

---

# Discipline rule 3 — metadata

Record it *while you remember it*. Minimum set:

```text
fan model / size:      Arctic F12, 120 mm
supply voltage:        12 V  (write down if you change it!)
nominal RPM:           ~1350 (from datasheet or strobe/audio check)
sensor axis vs shaft:  Z axis parallel to rotation axis
mount:                 2x zip-tie, frame corner, top-left
weight (imbalance):    M3 nut + tape, blade tip
date/desk/person:      2026-07-xx, desk 4, <name>
```

- In EI: use the **filename/label conventions** — `imbalance.desk4.01`
- Keep a `NOTES.md` next to your project — future-you is a different person

<!--
The RPM entry matters most: Module 5's spectral section asks everyone to find their fan's fundamental in the FFT, and the datasheet RPM lets you predict where it should be. Cheap RPM check: hold a phone mic near the fan and look at a spectrum app, or count the strongest low-frequency peak in tomorrow's FFT and work backwards. Metadata is also the difference between "we can merge datasets from 10 participants on Day 3" and "we have 10 incompatible datasets".
-->

---

# Ingestion recap — the Module 3 forwarder

- We reuse the **accel-forwarder firmware from Module 3** unchanged
  (LIS3DH ODR 400 Hz, polled at 250 Hz → `x\ty\tz` lines on USB serial @ 115200)
- On the laptop:

```bash
edge-impulse-data-forwarder
# → login, select project, name axes: accX, accY, accZ
```

- Forwarder auto-detects the sample rate from line timing — verify it reports **≈ 250 Hz**
- Then: EI Studio → **Data acquisition** → device shows up → set label + length → *Start sampling*

<!--
Do not re-flash or rewrite anything — this is the payoff of Module 3. If someone's forwarder detects, say, 160 Hz instead of 250 Hz, their firmware loop has timing jitter (delay() instead of a timer) — fix in firmware, not by lying to EI. A rate pinned near 100 Hz with a stair-stepped waveform is the other classic: the LIS3DH ODR is below the polling rate, so each sample is read several times. The axis names matter: keep accX/accY/accZ consistent across the whole class so projects can be merged later.
-->

---

# Recording in Edge Impulse Studio

![height:420](../brightspace-export/_ontent/i39a275e2-29c7-45a0-b627-a4e30b2cc8db/Screenshot%202026-05-14%20at%2010.33.38.png)

<!-- Reused EI screenshot (May 2026, HW-agnostic UI) from the old anomaly exercise — shows impulse design page; usable as-is since no Photon hardware is visible. -->

<!--
Walk the UI live in parallel: Data acquisition tab, label field, sample length 20000 ms, frequency 250 Hz. Show one recording end-to-end, then let them loop. The screenshot shows where this data eventually flows — the impulse design page — as a teaser for what happens after lunch.
-->

---

# 🧪 Lab step 2 — record the dataset (~60 min)

**`exercises/module4-fan-dataset/README.md`** → sections 3–5

- 5 states × 4 interleaved rounds × 20 s = **~27 min of machine time**
- Label in Studio exactly as the state table says; metadata per the template
- Run the two sanity checks (next slides) **as you go**, not at the end
- **Done when:** the 12-item dataset-quality checklist is all ✅

<!--
The main event — most of the module's remaining time. Interleaving rounds is non-negotiable (rule 1); the sanity-check slides coming up are meant to be used DURING recording, so nobody discovers a dead axis after 27 minutes of collection. Fault states that look identical to normal in the feature explorer get strengthened now, not tomorrow.
-->

---

# Sanity check 1 — look at the raw data

For every state, click a sample in EI and **eyeball the waveform**:

- `off` → flat lines (± noise ~ a few mg)
- `normal` → periodic ripple, stable amplitude
- `imbalance` → clearly larger periodic ripple
- `scrape` → spiky, irregular
- `blocked` → similar to normal but different level (be sceptical!)

**If two states look identical → make the physical fault stronger *now*, not on Day 3.**

<!--
"Blocked" is the state most likely to be weak in amplitude features — its main signatures (RPM shift, flow noise) are subtle in accelerometer amplitude. That's intentional: it motivates spectral features in Module 5 (RPM shift is invisible to RMS but obvious in the FFT). If a participant's blocked state is truly indistinguishable, options: block more of the intake, or lower the supply voltage for that scenario — but then document it in metadata.
-->

---

# Sanity check 2 — the feature explorer

- Quick impulse: **Spectral Analysis** block on 2 s windows → **Generate features**
- The **feature explorer** projects all windows to 3-D (UMAP-style)
- What you want: 5 visibly distinct clusters (off will be far away)
- What clusters *touching* means: those two states will confuse the classifier

![height:300](../brightspace-export/_ontent/i39a275e2-29c7-45a0-b627-a4e30b2cc8db/Screenshot%202026-05-14%20at%2010.48.04.png)

<!-- Reused EI screenshot (live classification view) as visual placeholder for the feature-explorer step. TODO: capture an actual feature-explorer screenshot from a fan project — the old export has no feature-explorer image. -->

<!--
We're using EI's DSP as a free visual QA tool before we've taught features — that's fine, Module 5 opens the box. The feature explorer is the fastest data-quality feedback loop in the whole toolchain: seconds after recording you see whether your dataset is separable. Live-demo clicking a stray point: it shows which recording/window it came from — perfect for hunting mislabelled or corrupted samples.
-->

---

# Common failure modes (and fixes)

| Symptom | Cause | Fix |
|---|---|---|
| Forwarder reports wrong Hz | `delay()`-based loop timing | timer-driven sampling (Module 3 code) |
| All classes overlap in explorer | Soft mounting | zip-tie tighter, remount |
| `normal` forms 2 clusters | Mount changed mid-session | re-record one cluster's files |
| Clipped waveform at ±4 g | Scrape too aggressive | lighter touch |
| One class much fewer windows | Uneven recording | top up recordings |
| Perfect separation incl. blocked | Might be genuinely good — or leakage | check session interleaving |

<!--
Print this table into the exercise README as well (it's there). The "normal forms two clusters" case is the classic one to debug live: it almost always means the physical setup changed between recordings — which is exactly what the interleaving rule is designed to surface early.
-->

---

# Optional extension — parallel audio

- RAK18000 PDM mic (IO slot, DATA `WB_IO3`, CLK `WB_IO4`) can record the same states **acoustically**
- Audio at 16 kHz captures what 250 Hz vibration cannot: blade-pass, flow turbulence, bearing hiss
- Workflow (from Module 3): PCM dump → WAV → `edge-impulse-uploader`
- **Do this only if your vibration dataset is done and clean**

<!--
Keep this strictly optional — Day 2 is accelerometer-centric by design; audio returns on Day 3 for those interested. One accurate modality beats two sloppy ones. If a fast group finishes early, parallel audio of the same 5 states makes an excellent Day 3 comparison dataset.
-->

---

# Exercise hand-off — the fan lab

**`exercises/module4-fan-dataset/README.md`**

1. Build the rig: mount WisBlock on fan (photo checklist)
2. Verify the forwarder path (Module 3 firmware, 250 Hz)
3. Define the 5 states — physically prepare each fault
4. Record: ≥ 5 × 20 s per state, interleaved, metadata as you go
5. Label + train/test split in EI Studio
6. Feature-explorer sanity check
7. Run the **dataset-quality checklist** — all boxes ticked before lunch

⏱ Budget: ~2.5 h · Work in pairs, but **each project needs its own dataset**

<!--
Pairs share a fan and a rig but should each drive the recording of at least two states, and each EI project must hold the full 5-class dataset (EI data can be exported/imported between projects, or use collaborators on one project — either is fine, but say which). Circulate and inspect metadata notes — the checklist at the end of the README is the module's exit ticket.
-->

---

# Module 4 checkpoint

You now have:

- ✅ A physical condition-monitoring rig (sensor rigidly mounted on the machine)
- ✅ Five defined, reproducible machine states
- ✅ ≥ 250 labelled windows in Edge Impulse, split cleanly into train/test
- ✅ Metadata that lets anyone reproduce the recording
- ✅ Visual evidence (feature explorer) that the classes are separable

**Next (Module 5):** open the black box — *what* makes these classes separable, computed by hand in Python and then in C on the nRF52840.

<!--
Segue: the feature explorer just showed clusters, but EI computed features for us. Module 5 asks: which numbers, exactly? And can we compute the same numbers in 20 lines of C on a Cortex-M4F? Break here.
-->
