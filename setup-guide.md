# Tool Setup Guide — TinyML Course (RAK4631 WisBlock)

Complete this **before Day 1** (Module 2 walks through it, but pre-installing saves an hour of downloads on hotel Wi-Fi). Allow ~45 minutes.

You need: a laptop (Windows/macOS/Linux) with admin rights, a USB-C data cable, and your WisBlock kit.

---

## 1. VS Code + PlatformIO

1. Install [VS Code](https://code.visualstudio.com/).
2. In VS Code: Extensions (⇧⌘X / Ctrl+Shift+X) → search **PlatformIO IDE** → Install. Wait for "PlatformIO Core installed" (a few minutes).
3. Restart VS Code. You should see the PlatformIO alien-head icon in the sidebar.

## 2. RAK4631 board support (one-time patch)

PlatformIO's Nordic platform doesn't ship the RAK4631 board definition — RAK provides a patch.

1. PlatformIO Home → Platforms → Embedded → install **Nordic nRF52**.
2. Create a throw-away project with any nRF52 board (e.g. *Adafruit Feather nRF52840 Express*) and hit Build once — this downloads the `framework-arduinoadafruitnrf52` package the patch modifies.
3. Download [RAK_PATCH.zip](https://github.com/RAKWireless/WisBlock/tree/master/PlatformIO) (linked from RAK's PlatformIO README).
4. Unzip into your PlatformIO core folder (`~/.platformio` on macOS/Linux, `%USERPROFILE%\.platformio` on Windows) and run the patch script:
   ```bash
   cd ~/.platformio
   unzip ~/Downloads/RAK_PATCH.zip -d rak_patch
   cd rak_patch && python3 ./rak_patch.py
   ```
   This installs the `wiscore_rak4631` board JSON and the `WisCore_RAK4631_Board` variant.
5. Verify: create a new project, board **WisCore RAK4631**. Your `platformio.ini` should read:
   ```ini
   [env:wiscore_rak4631]
   platform = nordicnrf52
   board = wiscore_rak4631
   framework = arduino
   monitor_speed = 115200
   ```

### First flash (blink)

```cpp
#include <Arduino.h>
void setup() { pinMode(LED_GREEN, OUTPUT); }
void loop()  { digitalWrite(LED_GREEN, !digitalRead(LED_GREEN)); delay(500); }
```

- Upload uses `adafruit-nrfutil` over the USB serial port (installed automatically).
- **If upload fails / no port:** double-press the RESET button on the base board — the green LED breathes and a `RAK4631` USB drive appears (bootloader mode) — then upload again.
- Serial monitor: 115200 baud.

## 3. Edge Impulse

1. Create a free account at [studio.edgeimpulse.com](https://studio.edgeimpulse.com).
2. Install [Node.js LTS](https://nodejs.org/) (≥ v20).
3. Install the CLI tools:
   ```bash
   npm install -g edge-impulse-cli
   ```
4. Verify: `edge-impulse-data-forwarder --version`.

We use the **data forwarder** (streams sensor CSV from the board's serial port into your EI project) and the **uploader** (`edge-impulse-uploader` for WAV files). There is no official EI firmware for the RAK4631 — we write our own forwarder sketches in Module 3; that's a feature of the course, not a bug :-).

## 4. Python environment

Any recent Python (≥3.10). Recommended: a dedicated environment.

```bash
python3 -m venv ~/tinyml-env
source ~/tinyml-env/bin/activate        # Windows: tinyml-env\Scripts\activate
pip install numpy pandas matplotlib scikit-learn jupyterlab emlearn tensorflow
```

- `emlearn` converts scikit-learn models to C headers (Modules 6–7).
- `tensorflow` is only needed for Keras notebooks (Modules 1, 7, 8); skip if disk-constrained and use Google Colab instead.
- Test: `jupyter lab` opens in your browser; `python -c "import emlearn; print(emlearn.__version__)"`.

## 5. Serial terminal (optional but handy)

Any of: PlatformIO's built-in monitor, `screen`, PuTTY, or the [Serial Studio](https://serial-studio.github.io/) plotter for visualising live sensor data.

## 6. Pre-course checklist

- [ ] PlatformIO builds and flashes blink to the RAK4631 (LED blinks)
- [ ] Serial monitor shows output at 115200
- [ ] `edge-impulse-data-forwarder --version` works
- [ ] Edge Impulse account created
- [ ] `jupyter lab` starts, `import sklearn, emlearn` succeeds

**Stuck?** Bring the problem to Day 1 — Module 2 has buffer time for setup triage.

---

## Hardware quick reference

| Item | Detail |
|---|---|
| Core | RAK4631: nRF52840 (64 MHz M4F, 256 KB RAM, 1 MB flash) + SX1262 LoRa |
| Base | RAK19007: 1 core slot, 1 IO slot, 4 sensor slots (A–D) |
| Accelerometer | RAK1904 (LIS3DH) in **sensor slot A** — I²C `0x18`, interrupt on `WB_IO5` |
| Microphone | RAK18000 (2× MP34DT06J PDM, stereo) in **IO slot** — PDM DATA `WB_IO3`, PDM CLK `WB_IO4` |
| LEDs | `LED_GREEN`, `LED_BLUE` |
| USB | USB-C, CDC serial + DFU |

Assembly: modules key onto the board — align the connector and the mounting-screw hole; never force. Power off (unplug USB) before adding/removing modules.
