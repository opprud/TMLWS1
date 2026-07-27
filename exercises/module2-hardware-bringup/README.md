# Module 2 Lab — RAK4631 WisBlock Bring-up

Three PlatformIO projects, **in this order** — each one isolates a different failure layer, so don't skip ahead:

| # | Project | Proves | ~Time |
|---|---|---|---|
| 1 | [`blink/`](blink/) | toolchain + board patch + flashing | 15 min |
| 2 | [`accel-read/`](accel-read/) | I²C, sensor power, LIS3DH library | 20 min |
| 3 | [`mic-level/`](mic-level/) | PDM peripheral, DMA double-buffering | 25 min |

**Prerequisites:** the [setup guide](../../setup-guide.md) completed — VS Code + PlatformIO + the RAK board patch. If the patch isn't applied, exercise 1 fails at the first build with `unknown board`, and that's your cue.

**Hardware before you start (USB unplugged!):**
- RAK4631 core in the core slot, screwed down
- RAK1904 accelerometer in **sensor slot A**, screwed down
- RAK18000 microphone in the **IO slot**, screwed down

**Documentation:**
- [RAK4631 CPU & LoRa module](https://docs.rakwireless.com/product-categories/wisblock/rak4631/overview)
- [RAK1904 Accelerometer](https://docs.rakwireless.com/product-categories/wisblock/rak1904/overview)
- [RAK18000 microphone](https://docs.rakwireless.com/product-categories/wisblock/rak18000/overview)
---

## Exercise 1 — Blink & serial hello (`blink/`)

The embedded "hello world": build, flash, watch an LED, read serial. If this works, your entire toolchain works.

### Steps

1. In VS Code: **File → Open Folder** → `exercises/module2-hardware-bringup/blink/`
2. Wait for PlatformIO to initialise the project (bottom toolbar appears).
3. **Build** (checkmark icon). First build downloads the toolchain — a few minutes.
4. Plug in the board. **Upload** (arrow icon).
5. **Monitor** (plug icon), 115200 baud.

### Expected output

Green LED toggles every 500 ms and the monitor shows:

```
RAK4631 alive — hello from PlatformIO!
blink #1
blink #2
...
```

6. Now do the `TODO(student)` items in `src/main.cpp` — alternate LEDs, heartbeat pattern, timing measurement.

---

## Exercise 2 — Accelerometer over I²C (`accel-read/`)

Read the RAK1904 (ST LIS3DH) at address `0x18` using the Adafruit LIS3DH library. The `lib_deps` in `platformio.ini` pulls the library (plus BusIO and Unified Sensor) automatically on first build.

> **The one thing everyone forgets:** WisBlock sensor slots are power-gated. `WB_IO2` must be driven HIGH before the sensor exists on the bus. It's the first thing `setup()` does — leave it alone.

### Steps

1. Open `accel-read/` as a new VS Code folder, build, upload, monitor.
2. You should see live readings (below). Hold the board flat, then rotate it — gravity moves between axes.
3. Work through the `TODO(student)` items: gravity hunting, magnitude, clipping at ±2 g, shake detector.

### Expected output

```
RAK1904 / LIS3DH bring-up
Range: +/-4 g. Streaming...
X: 0.12  Y: -0.24  Z: 9.79 m/s^2
X: 0.10  Y: -0.19  Z: 9.83 m/s^2
...
```

At rest: one axis ≈ ±9.81 m/s², the others near 0. If you see values pinned at ≈ ±39.2, you're clipping the ±4 g range (are you shaking it? stop shaking it).

---

## Exercise 3 — PDM microphone level meter (`mic-level/`)

Bring up the RAK18000 microphone using the nRF52840's hardware PDM peripheral via the `nrfx_pdm` driver (bundled with the Adafruit BSP — no extra library). The peripheral demodulates the 1-bit mic stream to 16-bit PCM @ 16 kHz and DMAs it into RAM; the sketch double-buffers and prints an RMS level + bargraph 10× per second.

Key facts baked into the code:

| Item | Value |
|---|---|
| PDM DATA | `WB_IO3` |
| PDM CLK | `WB_IO4` |
| Clock/ratio | 1.28 MHz ÷ 80 → **16.000 kHz** (fallback 1.032 MHz ÷ 64 ≈ 16.125 kHz) |
| Mode | mono, left channel, gain 40 |

### Steps

1. Open `mic-level/`, build, upload, monitor.
2. Sit quietly: short bars. Talk: medium bars. Clap: wall of `#`.
3. Do the `TODO(student)` items: dBFS conversion, clipping check, clap-light, gain experiment.

### Expected output

```
RAK18000 PDM bring-up — RMS level meter
Sampling at 16 kHz. Make some noise...
RMS 42   
RMS 38   
RMS 812  ########
RMS 5120 ###################################################
```

(Quiet room: RMS below ~100. Speech at arm's length: several hundred to a few thousand.)

### Read the code — it matters later

The **double-buffer pattern** in `pdm_handler()` (`buffer_requested` → hand over the next buffer; `buffer_released` → flag it for `loop()`) is reused verbatim in Module 3's recorder, and on Day 3 it carries live inference. Two minutes reading it now pays off twice.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Build: `Error: Unknown board ID 'wiscore_rak4631'` | RAK patch not applied — setup guide §2; re-run `rak_patch.py`, restart VS Code |
| Upload: timeout / port not found | **Double-press RESET** → green LED breathes + `RAK4631` drive appears → upload again |
| Upload works, monitor shows nothing | wrong baud (use 115200); or reopen the monitor — USB re-enumerates after every flash |
| `Failed to find LIS3DH` / ERROR at 0x18 | module not seated / wrong slot (must be **A**) / `WB_IO2` line removed from the sketch |
| Accel values frozen | you're reading before the data rate ticks — or the module isn't screwed down and lost contact |
| Mic: build error around `nrfx_pdm` | uncomment `build_flags = -DNRFX_PDM_ENABLED=1` in `platformio.ini` (see `VERIFY` note) |
| Mic: RMS is always 0 | DATA/CLK swapped — the config must be `NRFX_PDM_DEFAULT_CONFIG(WB_IO4, WB_IO3)`, CLK first |
| Mic: constant huge RMS | mic module not seated; or gain cranked with the monitor's fan next to it (yes, really) |
| Everything broken on one laptop | borrow a neighbour's board to bisect: board vs laptop. Flag the instructor early. |

**Done early?** Combine 2 + 3: print accel magnitude *and* mic RMS on one line. You've just built the sensor front-end of a condition-monitoring node — Module 3 gives its data somewhere to go.
