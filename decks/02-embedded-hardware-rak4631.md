---
marp: true
theme: tinyml-clean
paginate: true
---

<!-- _class: title -->

# Module 2
# Embedded Hardware: RAK4631 WisBlock

**TinyML — Condition Monitoring on Microcontrollers**
Day 1 · Module 2 of 9

<!--
Module 2: the hardware. Everyone should have a WisBlock kit box in front of them — don't open it yet, there's an assembly ritual with rules. Goals for this module: understand what the nRF52840 gives us and what it doesn't, get the PlatformIO toolchain confirmed working on every laptop, and bring up all three peripherals we'll use for the rest of the course: LED, accelerometer, microphone. If your pre-course setup worked, you're 20 minutes from blinking. If not, this module has triage time built in.
-->

---

## Module 2 = the embedded half of TinyML

![w:720](assets/reddi/1-3-2-tinyml-puzzle.png)

<sub>Figure: TinyML on edX (HarvardX), V.J. Reddi et al. — used with permission</sub>

<!--
Orientation: Module 1 was the machine-learning puzzle piece; this module is the embedded-systems piece — the constraints, the toolchain, the peripherals. When the two pieces click together you get TinyML, and by the end of today they will have clicked: an ML-ready data pipeline running on this exact hardware.
-->

---

## The brain: nRF52840 (on the RAK4631 core)

| Spec | Value | TinyML relevance |
|---|---|---|
| CPU | Cortex-M4**F** @ 64 MHz | hardware float — features & NN math |
| RAM | **256 KB** | model + buffers + stack live here |
| Flash | **1 MB** | code + model weights |
| PDM peripheral | ✅ | digital microphones, zero CPU cost |
| EasyDMA | ✅ | peripherals move data while CPU sleeps |
| Radio | BLE 5 (+ SX1262 LoRa on module) | ship *verdicts*, not raw data |

<!--
The spec sheet, annotated with why-we-care. The F in M4F matters: hardware floating point means we don't pay a 10x penalty for float math in feature extraction and NN inference. 256 KB RAM is the number to tattoo somewhere — every buffer and model fights for it. The PDM peripheral is the star of this module's finale: it demodulates the digital microphone bitstream in silicon and DMAs finished 16-bit samples into RAM while the CPU does literally nothing. The LoRa radio we won't use in-course, but it's the natural "ship the verdict" channel in a real deployment — one anomaly flag per hour over LoRaWAN beats streaming kilohertz data.
-->

---

## RAM vs flash — the two budgets

- **Flash (1 MB):** your code + the BSP + **model weights**. Written at upload.
- **RAM (256 KB):** stack, heap, sensor buffers, **model activations**.

Rules of thumb:

- 2 s of 16 kHz 16-bit audio = **64 KB RAM** — a quarter of everything
- 10k-param float32 model = 40 KB flash + activations in RAM
- Peak RAM usage happens *inside* inference — not visible in the map file

<!--
Two separate budgets, and people conflate them. Flash is roomy — a megabyte holds a lot of model. RAM is the scarce one, and audio eats it fastest: the 64 KB for two seconds of audio comes back as a design constraint in module 3's mic-record exercise. The sneaky one is peak activation memory during NN inference — intermediate layer outputs that exist only transiently, so the linker map won't warn you. Day 3's efficiency-metrics material makes this precise; today just plant the two-budgets idea.
-->

---

## WisBlock: embedded Lego

A modular system — no soldering, no breadboard, no wiring errors:

- **Core** module — CPU + radio (our RAK4631)
- **Base** board — power, USB, slots (our RAK19007)
- **Sensor** modules — small, I²C/SPI, slots A–D
- **IO** modules — larger, more pins (our microphone)

The old course wired sensors on breadboards. You get connectors. You're welcome.

<!--
WisBlock philosophy: standardised slots, keyed connectors. The previous edition of this course had students wiring an accelerometer breakout to a Photon 2 on a breadboard — reliable source of swapped SDA/SCL and 45 minutes of debugging per class. Here the connector physically enforces correctness. Trade-off: you're inside RAK's module catalogue, but the catalogue includes exactly what condition monitoring needs.
-->

---

## Your kit

| Part | What | Where |
|---|---|---|
| RAK4631 | nRF52840 + SX1262 core | core slot |
| RAK19007 | base board, USB-C | — |
| **RAK1904** | LIS3DH 3-axis accelerometer | **sensor slot A** |
| **RAK18000** | 2× MP34DT06J PDM microphones | **IO slot** |
| 120 mm PC fan | your "pump" | Day 2 |

<!-- TODO: photo of the assembled kit — re-shoot: old-course photos are Photon2 breadboard (brightspace-export/_ontent/i15ac4701-536e-48d2-940d-a4071acfb016/IMG_9114_20260206084835320.jpeg is the old one, do NOT reuse) -->

<!--
Inventory check against the box contents. Core into the core slot, accelerometer into sensor slot A specifically — the exercise code assumes the I2C address that slot A wiring gives — and the microphone into the single IO slot, which it needs for its pin count. The fan stays boxed until tomorrow; it's the target machine, not a course snack-cooling device. Slide needs a proper photo of the assembled RAK stack — old course photo is Photon2-era and useless here.
-->

---

## Assembly rules (there are only three)

1. **USB unplugged** while adding/removing modules
2. Align the connector **and** the mounting-screw hole — the module only fits one way
3. **Never force it.** If it needs force, it's the wrong slot or wrong orientation

Then: screw the modules down. Vibration sensing on a machine that vibrates — loose modules make their own dataset.

<!--
Assembly time — 5 minutes. Power off is real: hot-plugging modules can kill them. The keying means the connector plus screw hole make wrong orientation geometrically impossible, so anyone applying force is applying it to the wrong slot. The screw joke is not a joke: from tomorrow this stack sits on a vibrating fan, and a rattling module adds its own resonances to your dataset. Walk the room and eyeball every assembled stack before anyone powers up.
-->

---

## RAK1904 — the accelerometer

- ST **LIS3DH**, 3-axis MEMS accelerometer
- I²C address **0x18**, interrupt line on `WB_IO5`
- Range: ±2/4/8/16 g — we use **±4 g**
- Data rate: 1 Hz – 5.3 kHz — we use **ODR 400 Hz, polled at 250 Hz**
- Driver: **Adafruit LIS3DH** Arduino library (plus BusIO + Unified Sensor)

⚡ Gotcha: sensor slots are power-gated — drive **`WB_IO2` HIGH** first!

<!--
Our vibration sensor. LIS3DH is a workhorse — the same Adafruit library from the maker world drives it, so no register-level driver writing today (the old course's ADXL343 exercise did raw registers; educational, but not where our time goes). Why ±4g: fan vibration is small, ±2g would also work, but ±4g gives headroom for handling knocks without clipping while keeping resolution. The WB_IO2 gotcha is THE classic WisBlock support-forum question: the 3V3_S rail feeding the sensor slots is switched by that pin, so a sketch that forgets it finds no sensor at 0x18 and reports a "broken" module. It's in the exercise skeleton, clearly marked.
-->

---

## RAK18000 — the microphone

- 2× ST **MP34DT06J** PDM MEMS microphones (stereo — we use mono)
- Sits in the **IO slot**
- **PDM DATA = `WB_IO3`, PDM CLK = `WB_IO4`**
- 62.6 dB SNR, AOP 122.5 dBSPL — plenty for machinery

<!--
Our acoustic sensor. Two microphones for stereo, but mono is all condition monitoring needs — one channel of fan noise. The two pins on the slide are load-bearing: WB_IO3 data, WB_IO4 clock; they appear verbatim in the exercise code and misordering them yields perfect silence. Specs-wise these mics laugh at machinery noise levels — the acoustic overload point is 122 dBSPL, jet-engine territory.
-->

---

## PDM — how a digital microphone talks

- Mic outputs a **1-bit stream** at MHz rate: density of 1s ∝ sound pressure
- No analog signal path, no ADC, cheap and noise-immune
- The nRF52840 **PDM peripheral** filters + decimates in hardware:

```
1-bit @ 1.28 MHz  ── ÷80 (hardware) ──►  16-bit PCM @ 16 kHz
```

- CPU cost: **zero**. Samples appear in RAM via EasyDMA.

<!--
One theory slide on PDM because it demystifies the config values in the exercise. Pulse density modulation: a 1-bit stream where the density of ones tracks the waveform — squint at it and it IS the waveform, just very fast and very coarse. Divide the numbers live: 1.28 MHz clock, hardware decimation ratio 80, gives exactly the 16 kHz PCM audio people know. And the CPU never touches a bit of it until finished samples land in RAM by DMA — that's EasyDMA earning its keep, and it's why a 64 MHz chip can record audio while doing other work.
-->

---

## Toolchain: VS Code + PlatformIO

- **PlatformIO** — package manager + build system for ~1500 boards
- Reproducible: `platformio.ini` pins platform, board, libraries
- One quirk: RAK4631 isn't in the official registry → **RAK patch** (you did this in the setup guide)

```ini
[env:wiscore_rak4631]
platform  = nordicnrf52
board     = wiscore_rak4631
framework = arduino
monitor_speed = 115200
```

<!--
The toolchain, which most of the room pre-installed. PlatformIO's pitch over the Arduino IDE: dependencies declared in a text file, so "works on my machine" becomes "works on every machine" — lib_deps lines in today's exercises pull exact library versions automatically. The RAK patch (board JSON + variant dropped into ~/.platformio) is the one non-standard step; it's setup-guide section 2. Quick hands-up: who has NOT successfully built anything yet? Those people pair up with a neighbour who has, and I'll triage during the blink exercise.
-->

---

## Anatomy of `platformio.ini`

```ini
[env:wiscore_rak4631]
platform  = nordicnrf52          ; toolchain + chip support
board     = wiscore_rak4631      ; pin map, memory layout (from RAK patch)
framework = arduino              ; Adafruit nRF52 core
monitor_speed = 115200           ; serial monitor baud

lib_deps =                       ; auto-installed, version-locked
    adafruit/Adafruit LIS3DH
    adafruit/Adafruit BusIO
    adafruit/Adafruit Unified Sensor
```

<!--
Line-by-line, because this file is the whole project configuration. Platform = compiler and chip package; board = the definition the RAK patch installed, carrying the pin names like WB_IO2 and LED_GREEN; framework arduino here means the Adafruit nRF52 core, a mature port with proper USB CDC. lib_deps is the piece to admire: the accelerometer exercise needs three Adafruit libraries and nobody will click through a library manager — first build fetches them. This exact block appears in each exercise skeleton.
-->

---

## Arduino on nRF52: what the BSP gives you

- `setup()` / `loop()`, `digitalWrite`, `Wire` (I²C), `SPI`, `Serial` (USB CDC)
- WisBlock pin names: `WB_IO1..7`, `LED_GREEN`, `LED_BLUE`
- FreeRTOS underneath (`delay()` actually sleeps — low power for free)
- Bundled **nrfx** drivers for bare-metal peripherals — that's our PDM path

<!--
What "framework = arduino" buys on this chip. Familiar Arduino API on top; the WisBlock variant adds sane pin names. Two things worth flagging: FreeRTOS runs underneath, so delay() genuinely sleeps the CPU instead of burning a busy-loop — relevant when someone asks about battery life. And the escape hatch: the Adafruit BSP bundles Nordic's nrfx driver layer, so when Arduino has no API for something — like the PDM peripheral — we call nrfx directly from an Arduino sketch. Exactly what the mic exercise does; no framework-switching required.
-->

---

## Flashing & the bootloader dance

- Upload = `adafruit-nrfutil` over USB serial (automatic)
- Board stuck / no port? **Double-press RESET** →
  green LED breathes, `RAK4631` USB drive appears = bootloader mode → upload again
- Serial monitor: **115200 baud**. Note: USB serial re-enumerates after reset —
  give it a second, reopen the monitor

<!--
The mechanics of getting code on. Normally: click upload, the tool reboots the board into bootloader, flashes, reboots back. When it goes wrong — and with ten laptops it will go wrong somewhere — the fix is the double-press: two quick taps on RESET, breathing green LED, and a USB mass-storage device appears; the board waits patiently for an upload. Teach it now as a normal move, not an emergency. Second habit: after every flash the USB serial disappears and re-enumerates, so a "dead" serial monitor usually just needs closing and reopening.
-->

---

## 🧪 Lab checkpoint 1 — blink (~15 min)

**`exercises/module2-hardware-bringup/blink/`**

- Build → upload → green LED blinks
- Upload fails? Double-press RESET (bootloader mode) and retry
- **Done when:** you've changed the blink rate and re-flashed — the loop works

<!--
First flash, deliberately before the sensor content is used: blink isolates the toolchain layer. If blink fails it's the PlatformIO patch or the cable, never I2C or PDM. Setup-triage happens here, not at minute 55. While stragglers flash, early finishers can read ahead — next slides cover serial and I2C, which the remaining two projects need.
-->

---

## Serial: your debugger, plotter, and data pipe

- `Serial.begin(115200)` + `Serial.print` — you know this
- PlatformIO monitor: the terminal icon, or `pio device monitor`
- Budget check: 115200 baud ≈ **11.5 KB/s** — remember this number in Module 3
- Tip: `while (!Serial) delay(10);` waits for the monitor (but blocks standalone boots!)

<!--
Serial is our everything today: printf debugging, live sensor viewing, and in module 3 the actual data-acquisition channel. Do the bandwidth math with the room now: 115200 baud, 10 bits per byte on the wire, about 11.5 kilobytes per second — remember that when we try to push 16 kHz 16-bit audio (32 KB/s) through it in an hour; the pipe is the plot constraint of module 3. The while(!Serial) idiom is in the skeletons so early prints aren't lost — but warn them: a board on a bare USB charger with that line waits forever. There's a TODO in the exercise about exactly that.
-->

---

## I²C on WisBlock

- `Wire` = the sensor-slot I²C bus; RAK1904 answers at **0x18**
- First move when a sensor sulks: **I²C scanner** (in the exercise repo)
- Checklist: module seated? slot A? **`WB_IO2` HIGH?**

```cpp
pinMode(WB_IO2, OUTPUT);
digitalWrite(WB_IO2, HIGH);   // power the sensor slots
delay(100);                   // sensor boot time
Wire.begin();
```

<!--
The I2C essentials before the accel exercise. This code block is the incantation — power the gated rail, give the sensor 100 ms to boot, then start the bus; it's the top of the exercise skeleton with a comment saying "do not delete". Debug flow when begin() fails: run the I2C scanner first. Scanner sees 0x18 → wiring is fine, bug is in your code. Scanner sees nothing → reseat the module, check the slot, check WB_IO2. That decision tree kills 90% of "my sensor is broken" reports.
-->

---

## 🧪 Lab checkpoint 2 — accelerometer (~20 min)

**`exercises/module2-hardware-bringup/accel-read/`**

- Power off → mount RAK1904 in **sensor slot A** → power on
- Build, upload, open serial monitor: live x/y/z at 115200
- **Done when:** z ≈ 9.8 m/s² flat on the desk, and it moves when you do

<!--
Second layer: I2C + the WB_IO2 power rail. The classic failure is forgetting that sensor slots are power-gated — the code handles it, but the troubleshooting box explains it, because tomorrow they write this init themselves. Tilt the board, watch gravity move between axes — cheap intuition for what the fan will do to these numbers.
-->

---

## 🧪 Lab checkpoint 3 — microphone (~20 min)

**`exercises/module2-hardware-bringup/mic-level/`**
*(blink was checkpoint 1, accelerometer checkpoint 2 — in order: each isolates one failure layer)*

- Power off → mount RAK18000 in the **IO slot** → power on
- Build, upload: live RMS level meter on the serial monitor
- Silence? Flip `NRF_PDM_EDGE_LEFTRISING` ↔ `LEFTFALLING` and re-flash
- **Done when:** the number jumps when you talk at the board

<!--
Lab hand-off, strictly in order because each step isolates a different failure layer: blink failing = toolchain/patch problem; accel failing = I2C/power/library problem; mic failing = PDM config problem. Skip blink and you can't tell which layer is broken. The skeletons compile as-is; TODOs make them do the real work. The mic-level finale is the crowd-pleaser — numbers that jump when you talk at the board — and quietly it's the same PDM engine that records the fan tomorrow. Setup-triage happens in parallel; flag me early, not at minute 55.
-->

---

## Common bring-up failures (from the trenches)

| Symptom | Likely cause |
|---|---|
| `wiscore_rak4631: unknown board` | RAK patch not applied to this PIO install |
| Upload timeout / no port | bootloader dance: double-press RESET |
| `Failed to find LIS3DH` | `WB_IO2` not HIGH · wrong slot · not seated |
| Mic reads all zeros | DATA/CLK swapped (`WB_IO3`/`WB_IO4`) |
| Serial monitor silent | wrong baud · monitor opened before re-enumeration |

<!--
The greatest-hits failure table — same list as the README troubleshooting boxes, shown here so the room knows these are *known* failures with known fixes, not personal hardware curses. Each row maps to one of the layers from the previous slide. Leave this slide up on the projector during the lab; it answers questions before they're asked.
-->

---

## Module 2 wrap-up

- ✅ Toolchain proven on every laptop
- ✅ nRF52840: 256 KB RAM, FPU, PDM + EasyDMA — and what that means
- ✅ Accelerometer streaming live data
- ✅ Microphone alive and measuring

**Next:** stop watching numbers scroll by — start **collecting datasets**. Edge Impulse enters the chat.

<!--
Checkpoint: every board in the room blinks, senses, and hears — the full hardware stack for the rest of the course is proven. What we don't yet have is data anywhere useful: numbers scrolling in a terminal are not a dataset. Module 3 builds the pipe from these sensors into Edge Impulse, where data gets labelled, organised and eventually turned into models. Short break first.
-->
