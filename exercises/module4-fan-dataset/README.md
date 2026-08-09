# Module 4 Exercise — The Fan Lab: Record a Condition-Monitoring Dataset

Build a vibration data-acquisition rig from your WisBlock kit and a 120 mm PC fan, define five machine states, and record a disciplined, labelled dataset into Edge Impulse. **This dataset is reused in Modules 5, 7 and 8 — quality here pays interest all week.**

⏱ Budget: ~2.5 h · Work in pairs (one rig), but every EI project must end up with the full 5-class dataset.

## Prerequisites

- Working Module 3 setup: the **accel-forwarder** PlatformIO project (LIS3DH @ 100 Hz → comma-separated `x,y,z` over USB serial @ 115200). Do **not** rewrite it — reuse it as-is from `exercises/module3-*/accel-forwarder/`.
- `edge-impulse-data-forwarder` installed and logged in (see `setup-guide.md`).
- An Edge Impulse project (create a fresh one: `fan-condition-monitoring`).
- Hardware: RAK4631 on RAK19007 base, RAK1904 in **sensor slot A**, USB-C cable, 120 mm PC fan + 5 V/12 V supply, zip-ties, tape, a small weight (M3 nut or a coin), cardboard.

## 1. Build the rig

1. Power off (unplug USB). Confirm the RAK1904 sits in **slot A** (I²C address `0x18`).
2. Mount the WisBlock **rigidly** on the fan frame using a 2.5mm screw, washer and nut
   **No foam tape, or zip ties** — soft mounts filter away exactly the vibration you want.
3. Note the **sensor axis orientation** relative to the fan's rotation axis (e.g. "Z parallel to shaft"). Write it down (metadata, step 4).
4. Tape the USB cable to the desk ~10 cm from the board (strain relief — a swinging cable adds fake low-frequency signal).
5. Place the fan on a firm surface. Rubber feet / a mousepad under the fan is fine (isolates desk noise) as long as it is the same for all recordings.

**Checkpoint:** flick a blade with the fan off — you should see a sharp spike in the serial plotter. If the trace barely moves, the mounting is too soft.

## 2. Verify the acquisition path

```bash
# terminal 1 — nothing needed on the device side; the Module 3 firmware is already flashed
edge-impulse-data-forwarder
```

- Select your `fan-condition-monitoring` project.
- Name the axes exactly: `accX, accY, accZ` (keep this identical across the whole class).
- **Expected output:** the forwarder detects a frequency of **≈ 100 Hz** (98–102 Hz is fine).

> **Troubleshooting**
> - *No serial port found*: close PlatformIO's serial monitor (only one program can own the port). On macOS the port is `/dev/cu.usbmodem*`.
> - *Detected frequency far from 100 Hz* (e.g. 60–80 Hz): your firmware paces sampling with `delay()`. Use the timer-driven Module 3 version.
> - *Board not enumerating*: double-press RESET → bootloader mode → re-flash.
> - *Forwarder connects to the wrong project*: run `edge-impulse-data-forwarder --clean` to re-select.

## 3. Define the five machine states

Prepare each fault physically **before** recording so you can interleave quickly:

| Label | Setup | Expect to see |
|---|---|---|
| `normal` | fan running free at nominal voltage | steady periodic ripple |
| `imbalance` | tape an M3 nut (or 2–4 cm tape blob) to **one** blade, near the tip | visibly larger ripple at rotation rate |
| `blocked` | cardboard covering ≥ 80 % of intake or exhaust | subtle: slight level/pitch change |
| `scrape` | zip-tie tip or stiff paper edge *lightly* touching blade tips | spiky, irregular bursts |
| `off` | fan unpowered | flat noise floor |

Rules:

- Change **one thing** per state; same fan, same mounting, same voltage throughout.
- `scrape` = light touch only. Don't jam objects into the fan.
- If you change the supply voltage for any reason, that's a new dataset — record it in metadata and stay consistent.

## 4. Record the dataset — with discipline

Target: **≥ 5 recordings × 20 s per state** (≥ 100 s/state → ≥ 50 two-second windows/state).

In EI Studio → **Data acquisition**:

- Sample length: `20000` ms · Frequency: 100 Hz (auto) · Label: the state name, exactly as in the table.

Procedure:

1. **Interleave** the states: record one sample of each state, then repeat the cycle 5×. Do **not** record all of one state back-to-back.
2. Between repetitions of the same state, **vary something legitimate**: re-stick the imbalance weight at a slightly different position, power-cycle the fan, re-seat the blockage cardboard.
3. Give the fan ~5 s to reach steady state after each change before hitting record.
4. Keep hands off the desk while recording.
5. Maintain `NOTES.md` **as you go**:

```text
fan model / size:      <e.g. Arctic F12, 120 mm>
supply voltage:        <e.g. 12 V>
nominal RPM:           <from datasheet — you will verify it in Module 5's FFT>
sensor axis vs shaft:  <e.g. Z parallel to rotation axis>
mount:                 <e.g. 2x zip-tie, frame corner top-left>
imbalance weight:      <e.g. M3 nut + tape, blade tip>
scrape object:         <e.g. zip-tie tip, touching at intake side>
blockage:              <e.g. cardboard, ~90 % of intake>
date / desk / person:  <...>
deviations:            <anything you changed mid-session>
```

## 5. Train/test split

- EI Studio → **Data acquisition** → *Train / test split* (aim ~80/20), **or** manually move the *last* recording of each state to the test set (⋮ menu → *Move to test set*).
- The split boundary must be **whole recordings**, never windows — adjacent windows from one recording are near-duplicates, and leakage here fakes your accuracy for the rest of the course.
- From now on: the test set is quarantined. Don't browse it during Module 5.

## 6. Sanity check with the feature explorer

1. **Create impulse**: window size `2000` ms, window increase `1000` ms (50 % overlap) → add **Spectral Analysis** block (defaults) → add any learning block (we won't train it yet) → Save.
2. **Spectral features** page → *Generate features*.
3. Inspect the **feature explorer** (3-D projection of all windows):
   - `off` should sit far from everything.
   - `scrape` and `imbalance` should form their own regions.
   - `blocked` vs `normal` may overlap somewhat — that is expected at 100 Hz and is exactly what Module 5's spectral features attack. But if they are *identical*, strengthen the blockage now.
4. Click outlier points — the explorer shows which recording/window they came from. Investigate: mislabelled? mount shifted? Delete or re-record bad files.

**Expected output:** 5 visually distinguishable groupings, ≥ 50 windows per class in training, ~10+ per class in test.

> **Troubleshooting**
> - *All classes overlap*: mounting too soft, or fan not actually running during "running" states. Fix rig, re-record.
> - *`normal` splits into two clusters*: setup changed mid-session (remount, voltage). Find the offending recordings (click points), re-record one cluster.
> - *A class has far fewer windows*: top up with more recordings — class imbalance hurts Day 3 training.
> - *Waveform clipped at ±4 g during scrape*: lighten the touch, re-record.

## 7. Dataset-quality checklist (exit ticket)

Tick every box before lunch — Modules 5/7/8 assume all of these:

- [ ] ≥ 5 recordings × 20 s for each of the 5 states (≥ 500 s total)
- [ ] States were recorded **interleaved**, not in blocks
- [ ] Something legitimate varied between same-state repetitions
- [ ] Sensor rigidly mounted; mounting unchanged for the whole session
- [ ] Forwarder frequency ≈ 100 Hz on every recording
- [ ] Axes named `accX, accY, accZ`
- [ ] Labels exactly: `normal`, `imbalance`, `blocked`, `scrape`, `off`
- [ ] Train/test split done **by recording**, ~80/20, every class present in test
- [ ] No clipping at ±4 g in any kept recording
- [ ] Feature explorer shows plausible clustering; outliers investigated
- [ ] `NOTES.md` metadata complete (incl. nominal RPM and axis orientation)
- [ ] Raw waveform of each class eyeballed and matches physical expectation

## Optional extension — parallel audio

Only if everything above is ✅: record the same five states with the RAK18000 PDM microphone (IO slot, DATA `WB_IO3`, CLK `WB_IO4`) using the Module 3 mic workflow (serial PCM dump → WAV → `edge-impulse-uploader`). Audio at 16 kHz captures blade-pass and flow noise that 100 Hz vibration cannot — you'll compare modalities on Day 3.
