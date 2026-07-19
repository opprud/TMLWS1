# TinyML Workshop — Condition Monitoring on a Microcontroller

A hands-on **3-day / 9-module** TinyML course. The running theme is **condition
monitoring of a 120 mm PC fan**: we take it end-to-end from raw sensor to an
on-device model —

> **sensor → dataset → features → model → deployment → anomaly detection → optimisation**

using vibration (accelerometer) and audio (PDM microphone) on a battery-class
Arm Cortex-M4 microcontroller.

Instructor: **Morten Opprud Jakobsen** · Aarhus University / Opprud.dk ·
`morten@ece.au.dk`

---

## Who this is for

Embedded / firmware / data engineers who want to run a full TinyML pipeline on
real hardware — not just a Colab notebook. You should be comfortable with C/C++
and a little Python. No prior machine-learning background is assumed; Day 1
builds it up from scratch.

## What you'll build

By the end you will have, on your own kit:

- A microcontroller streaming **100 Hz vibration** and **16 kHz audio**.
- A labelled dataset of *healthy* vs *faulty* fan states you captured yourself.
- Hand-written **feature extraction** in C that matches the Python reference
  bit-for-bit (validated against golden windows).
- A classifier deployed on-device three ways: **Edge Impulse**, **emlearn**
  (random forest → C), and a **quantised neural network**.
- An **anomaly detector** that flags fault states it was never trained on.
- A model shrunk with **quantisation + pruning** to fit the MCU's flash/RAM.

---

## Repository layout

| Path | What's in it |
|---|---|
| [`setup-guide.md`](setup-guide.md) | **Start here** — install toolchain, patch the board support, prepare your Python env. Do this *before* Day 1. |
| [`decks/`](decks/) | Slide sources (Marp markdown) + course theme. See [`decks/README.md`](decks/README.md) to render them. |
| [`exercises/`](exercises/) | One folder per module: labs, PlatformIO firmware, notebooks, scripts. See [`exercises/README.md`](exercises/README.md). |
| [`ATTRIBUTION.md`](ATTRIBUTION.md) | Third-party material, licences, and figure credits. |

## Course at a glance

| Day | Modules |
|---|---|
| **Day 1 — Foundations** | `01` Intro to TinyML & ML basics · `02` Embedded hardware & board bring-up · `03` Data acquisition |
| **Day 2 — Data & features** | `04` Fan data-acquisition lab · `05` Feature engineering · `06` ML frameworks for MCUs |
| **Day 3 — Models & deployment** | `07` Build & deploy models · `08` Anomaly detection · `09` Optimisation: quantisation & pruning |

Labs are **woven into the lecture flow** — each `🧪 Lab checkpoint` slide comes
right after the material that teaches it, rather than as one dump at the end.

---

## Hardware kit

The course targets the **RAK WisBlock** ecosystem (nRF52840, Arm Cortex-M4F):

| Part | Role | Key detail |
|---|---|---|
| **RAK4631** on **RAK19007** base | MCU core + baseboard | `platform = nordicnrf52`, `board = wiscore_rak4631`, `framework = arduino` |
| **RAK1904** (LIS3DH) | Accelerometer | I²C `0x18`, sensor slot A. Drive **`WB_IO2` HIGH** before `lis.begin()` (slot power gate). |
| **RAK18000** | PDM microphone | 16 kHz mono, DATA=`WB_IO3`, CLK=`WB_IO4` |

> ⚠️ The Arduino BSP needs a small **RAK board patch** — see
> [`setup-guide.md`](setup-guide.md) §2. Nothing compiles for the RAK4631
> without it.

## Course-wide conventions

Keep these consistent across firmware, notebooks, and slides — changing one in
isolation breaks the golden-window validation:

- **Accelerometer:** 100 Hz, windows of **200 samples (2 s), 50 % overlap**.
- **Feature math:** **population std (`/N`)** and **biased Fisher kurtosis** —
  the C and Python implementations match bit-for-bit.
- **Audio:** 16 kHz mono PCM.
- **Serial:** 115200 baud everywhere.

---

## Getting started

1. Read [`setup-guide.md`](setup-guide.md) and install everything **before Day 1**.
2. Skim [`exercises/README.md`](exercises/README.md) for the module map.
3. Each module folder has its own README with steps, expected output, and
   troubleshooting — work through them in order.

## Licence & attribution

Course material © Morten Opprud Jakobsen unless otherwise noted. Third-party
figures and code (edX/HarvardX, Jon Nordby, *Hands-On Machine Learning* / Géron)
retain their own licences and credits — see [`ATTRIBUTION.md`](ATTRIBUTION.md).
Some licensed lecture figures are **not redistributed** in this repo; see
[`decks/README.md`](decks/README.md).
