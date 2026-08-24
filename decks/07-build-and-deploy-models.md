---
marp: true
theme: tinyml-clean
paginate: true
---

<!--
Module 7 opens Day 3. Participants arrive with: a labelled fan dataset in Edge
Impulse (Module 4), a feature-engineering notebook + C feature code (Module 5),
and first deployments of emlearn XOR + an EI round-trip (Module 6).
Today we go end-to-end three times and make them race.
Timing: ~60 min slides, rest of the block is the three-track lab.
-->

<!-- _class: title -->

# Module 7
# Build a Model and Deploy It

**Three models, one fan, one scoreboard**
TinyML Course · Day 3

---

<!--
Day-boundary retrieval before anything new. Two minutes in pairs, then collect
answers cold. Answers: (1) blocked — its main signature is an RPM shift, a
*frequency* change; amplitude stays similar, so RMS is blind to it. Band
energies / the FFT expose it (Module 5). (2) The N vs N−1 convention:
numpy.std divides by N (population), pandas .std() by N−1 (sample) — the #1
Python-vs-C validation failure in Module 5. (3) Neural nets — they need
standardised inputs (offset/scale replicated in C); trees compare raw feature
values, no scaling at all. (4) A plain C header — the forest as nested
if/else (method='inline') or data arrays (method='loadable') that you
#include and call predict() on. Anyone who missed 1 should sit up during the
Model A slides: today it becomes a confusion matrix.
-->

## Warm-up — four questions from Day 2

1. Which fan state is nearly **invisible to RMS** alone — and which feature family exposes it?
2. Your C `std()` and pandas `.std()` disagree slightly. Why?
3. Trees or neural nets — which one needs **feature scaling**, and why?
4. What does `emlearn.convert(model).save()` actually produce?

*Two minutes with your neighbour — then we compare notes.*

---

<!--
Recap the pipeline drawn on Day 1. Everything left of "model" is done.
Point out that today the *same* dataset feeds three different models — that is
the only honest way to compare model families.
-->

## Where we are in the pipeline

```
sensor → acquisition → features → MODEL → deployment → decision
 (M2)      (M3–M4)      (M5)     (TODAY)    (TODAY)     (M8)
```

- Dataset: your PC-fan recordings — `normal`, `imbalance`, `blocked`, `scrape`, `off`
- Features: the 13-feature **time-domain baseline** — std / MAD / kurtosis / RMS per axis + resultant (Module 5)
- Frameworks: emlearn + Edge Impulse (Module 6)

**Today:** train three model families on the *same* data, deploy all of them to the RAK4631, and measure.

---

<!--
Set up the competition framing early — it keeps energy up during the lab.
Emphasise these are the three archetypes they will meet in industry.
-->

## The contenders

| | Model | Input | Toolchain | Deploys as |
|---|---|---|---|---|
| **A** | Random Forest | 13 handcrafted features | scikit-learn + emlearn | C header |
| **B** | Dense NN | DSP-block features | Edge Impulse Studio | C++ library |
| **C** | 1D-CNN | raw 3-axis windows | Edge Impulse Studio | C++ library |

Same fan. Same labels. Same MCU (nRF52840: 256 KB RAM, 1 MB flash, 64 MHz M4F).

**Question of the day: which one earns its place in a product?**

---

<!--
Refresh the dataset facts because the numbers drive every buffer size in the
firmware. If groups used different window settings in Module 5, they must keep
them consistent today — a mismatch between training window and firmware window
is the #1 silent failure.
-->

## Recap — the fan dataset

- 3-axis vibration from the RAK1904 (LIS3DH, sensor slot A, I²C `0x18`)
- Sampled at **250 Hz**, windowed into **500-sample windows** (2 s), 50 % overlap
- Five machine states = five class labels
- Train/test split done **by recording session**, not by window — no leakage

> Windows in training **must** equal windows in firmware. Write your numbers down now.

---

<!--
Model A theory. Open by acknowledging: this is the third time they meet a
random forest — it ranked features in Module 5 and classified XOR in Module 6.
Now the mechanics, properly. Keep it light — one slide of intuition. A decision
tree is a cascade of if-statements on features; a forest is a vote of many
trees trained on random subsets. Perfect mental model for embedded engineers:
it literally compiles to if-statements.
-->

## Model A — Random Forest

- A **decision tree** = learned cascade of `if (feature < threshold)` splits
- A **forest** = many trees, each trained on a random data/feature subset → majority vote
- Handles non-linear boundaries, ignores irrelevant features, hard to overfit with enough trees

```
if (rms_x < 0.13)          → off
else if (std_y < 0.02)     → normal
else if (kurt_z > 3.1)     → scrape
...  × 10 trees → vote
```

A random forest **is** embedded-friendly control flow.

---

<!--
Two killer properties for MCUs, both from Jon Nordby's emlearn deck (Module 6):
no feature scaling needed, and integer maths. Literature: trees are competitive
with deep learning on tabular/feature data at 10–100x less resources.
-->

## Why trees shine on microcontrollers

- **No feature scaling required** — splits compare raw values; skip the StandardScaler entirely
- **No multiplications** — inference is comparisons + branches; runs in integer maths
- **Tiny and predictable** — footprint ≈ number of decision nodes; worst-case latency ≈ tree depth
- emlearn: portable **header-only C99**, zero dependencies

> "Tree ensembles are competitive with deep learning on feature data at 10–100× fewer resources" — J. Nordby, *Practical TinyML with emlearn* (Module 6 deck)

---

<!--
The teachable gap. The 13-feature baseline is ALL time-domain — on purpose.
Module 5 spent its entire second half proving that one state's signature is a
frequency shift that amplitude statistics cannot see. Let them predict which
class suffers and write it on the worksheet BEFORE training; the scoreboard
grades the prediction later today. Expected answer: blocked (its RPM shift
leaves amplitude nearly unchanged — blocked↔normal confusion). If someone
asks about MAD: yes, Module 5 skipped it in the streaming path because it
costs a sort — here we classify one buffered window per inference, so the
batch path affords it. The baseline is the control group of today's
experiment, not an oversight.
-->

## Model A's feature set — spot the gap

The 13-feature baseline: std · MAD · kurtosis · RMS per axis, + resultant.

**All time-domain. Not one spectral feature.**

- Module 5 proved amplitude statistics are *frequency-blind*
- ❓ **Predict now, before training: which class will suffer in the confusion matrix?**
- Write your prediction on the worksheet — today's shoot-out will grade it

*(The gap is deliberate — this baseline is the control group.)*

---

<!--
Live-code feel: this is the whole training + conversion story. Point at the
dtype parameter — it foreshadows Module 9. Golden test vectors: re-use the
Module 5 validation methodology (Python vs C on the same static array).
-->

## Train → convert → header

```python
from sklearn.ensemble import RandomForestClassifier
import emlearn

clf = RandomForestClassifier(n_estimators=10, max_depth=8)
clf.fit(X_train, y_train)                # X = 13 fan features
print(clf.score(X_test, y_test))

cmodel = emlearn.convert(clf, method='inline')   # dtype: 'float' for now
cmodel.save(file='fan_model.h', name='fan_model')
```

- `fan_model.h` is plain C — `#include` it, done
- `dtype='int16_t'` etc. exists → we quantise trees in **Module 9**

---

<!--
The 4-step validation ladder from the old RF assignment — this picture is the
methodology backbone for the whole day. Validate each stage against the
previous one before touching live sensor data.
Figure is from the old course; content is HW-agnostic (no Photon visible in the
diagram itself, but re-check before print).
-->

## Deploy like an engineer — the 4-step ladder

![w:850](../brightspace-export/assignment/ide75a199-3e72-47aa-aafc-d89c6f275597/Screenshot%202025-03-18%20at%2021.01.521.png)
<!-- TODO: figure from old course (RF-on-Photon assignment). Diagram itself is HW-agnostic, but verify no Photon 2 branding; ideally re-draw with RAK4631. -->

1. Python features + Python model ✔ (notebook)
2. **C features + C model on your laptop** — same static window → same class?
3. C features + C model on the RAK4631, static test arrays
4. Live sensor data

---

<!--
Static-array validation — reuse the pattern from the old course: copy a window
of raw CSV data into a const C array and feed it through features + model.
This is "golden sample testing" and it saves hours of on-target debugging.
-->

## Golden test vectors

```c
// one 500-sample window of a known 'imbalance' recording, from CSV
static const float test_imbalance[500][3] = {
  { 0.012f, -0.981f, 0.033f },
  { 0.018f, -0.976f, 0.041f },
  /* ... exported by train_rf.py ... */
};
```

- Exported automatically by the training script
- Expected: `fan_model_predict(...) == IMBALANCE` **before** you trust live data
- Python and C features must agree to ~4 decimals (Module 5 method)

![bp right:30% w:350](../brightspace-export/assignment/ide75a199-3e72-47aa-aafc-d89c6f275597/Screenshot%202025-10-20%20at%2010.29.35.png)
<!-- TODO: screenshot shows Particle-era editor; re-capture in VS Code + PlatformIO. -->

---

<!--
Model B. Same features, different classifier. Show the old 8/16/3 architecture
— we keep it because it is small enough to read. The Keras plot figure comes
from the old assignment and is HW-agnostic.
Mention: in the lab they build this in EI Studio instead of Keras — the EI NN
block is exactly this kind of small dense net.
-->

## 🧪 Start lab track A now — RF training runs while we continue

**`exercises/module7-models/rf-features/`**

- `ei_json_to_csv.py` → `train_rf.py` → `fan_model.h` (a few minutes end-to-end)
- Leave the PlatformIO build for the lab block — just get the header generated
- **Done when:** `fan_model.h` exists and reports its size

<!--
Pipelined lab: track A's training is a background task on their laptop while the lecture continues with Model B. By the lab block, everyone has a generated header and the on-device work starts immediately. Anyone whose CSV conversion fails gets found now, not at minute 90.
-->

---

## Model B — Dense NN on features

![bg right:25% h:550](../brightspace-export/assignment/i1b47319e-6d63-4031-8466-8179c421eecf/dense_model_8_16.keras.png)

- Input: 13 features → **Dense 8 (ReLU) → Dense 16 (ReLU) → Dense 5 (softmax)**
- ~1 k parameters ≈ 4 KB as float32 — trivial for 1 MB flash
- Learns feature *combinations* the tree splits can't express smoothly
- In the lab: built visually in **Edge Impulse Studio** (Spectral Analysis → NN Classifier)

---

<!--
The one thing NNs need that trees don't: scaled inputs. Show the offset/scale
export trick from NN_w_selectedFeatures.ipynb — whoever does the Keras/AIfES
bonus track needs it; EI users get scaling inside the DSP block for free.
-->

## NNs need scaled inputs (trees don't)

```python
scaler = StandardScaler().fit(X_train)      # z = (x - mean) / std
```

```c
// exported from the notebook — apply before every inference
static const float offset[13] = { 0.0928f, 0.1283f, /* ... */ };
static const float scale[13]  = { 0.0952f, 0.1067f, /* ... */ };
for (int i = 0; i < 13; i++)
    features[i] = (features[i] - offset[i]) / scale[i];
```

- Forget this → the model happily predicts garbage (softmax always sums to 1!)
- Edge Impulse handles it inside the DSP block — one reason SaaS is comfortable

---

<!--
EI impulse design for model B. Walk the Studio flow: window size must match the
dataset; spectral analysis block computes RMS + spectral peaks/power in bands —
i.e. Module 5's features plus the frequency-domain ones we added for the fan.
-->

## Edge Impulse impulse design (Model B)

```
Time series data          Spectral Analysis        NN Classifier
window 2000 ms      →     (per-axis filter,   →    Dense 20 → 10 → 5
increase 500 ms           FFT, PSD features)       softmax
```

- **Spectral Analysis** = your Module 5 features, industrialised (RMS + FFT band powers — fan RPM harmonics!)
- Keep the window equal to your recorded window
- Train, inspect the confusion matrix, then **Live classification** before deploying

---

<!--
Model C — the "no feature engineering" pitch. Conv1D kernels slide over the raw
window and learn their own filters; show what the first conv layer learns
conceptually (edge/period detectors). Grid-search results from the old notebook:
bigger is NOT better — 3 filters + 16 dense units beat 8 filters + 64 units.
-->

## 🧪 Queue lab track B now — EI trains server-side

In your EI fan project:

- Impulse: Spectral Analysis → NN classifier (defaults are fine to start)
- Hit **train** — results wait for you; compare val. accuracy to track A later
- **Done when:** the training job is running

<!--
Same pipelining trick: EI's training is server-side, so queue it before the CNN content. If Module 6's kick-off export already exists this is a 2-minute variation, not new work.
-->

---

## Model C — 1D-CNN on raw windows

![bg right:22% h:550](../brightspace-export/assignment/ifee4da03-fe98-4b51-b18a-d32bec349f3d/cnn_model_3_6_8.keras.png)

- Input: raw **500 × 3** window — no handcrafted features
- `Conv1D(3, k=3) → MaxPool → Conv1D(6, k=5) → MaxPool → Flatten → Dense 8 → softmax`
- Kernels = **learned** feature extractors (period detectors, spike detectors…)
- Old-course grid search: small models won — 3 filters/16 units ≈ 80 %, 8 filters/64 units *worse* (overfit)

---

<!--
The honest trade-off table. This is the discussion slide — pause here.
Key point for condition monitoring: handcrafted spectral features encode domain
knowledge (RPM harmonics) that a small CNN must re-learn from limited data.
-->

## Handcrafted features vs raw data

| | Features + RF/NN | CNN on raw |
|---|---|---|
| Domain knowledge | encoded by *you* (RPM, harmonics) | must be *learned* from data |
| Data appetite | small datasets OK | wants much more data |
| MCU cost | feature calc + tiny model | bigger model, more RAM (activations) |
| Explainability | feature importances | low |
| New sensor/machine | re-engineer features | often just retrain |

**Fan verdict (spoiler):** with 20 min of data per class, features usually win. Verify it yourself.

---

<!--
Deployment path for B and C. The EI Arduino library export unzips straight into
PlatformIO's lib/ folder — PIO understands Arduino library layout. This is the
official EI-supported route that works without their firmware.
-->

## Deploying the EI models into PlatformIO

1. Studio → **Deployment** → *Arduino library* → Build → download zip
2. Unzip into your project's **`lib/`** folder:

```
fan-monitor/
├── lib/
│   └── Fan_Monitor_inferencing/     ← unzipped EI export
│       └── src/ (edge-impulse-sdk/, model-parameters/, tflite-model/)
├── src/main.cpp
└── platformio.ini
```

3. `#include <Fan_Monitor_inferencing.h>` — PlatformIO compiles the SDK automatically
<!-- VERIFY: exact header name is <ProjectName>_inferencing.h from your EI project name -->

---

<!--
The run_classifier pattern — this is the code they copy. signal_t wraps the
float buffer via a callback so the SDK can stream it without an extra copy.
Buffer layout is interleaved x,y,z — same order as the data forwarder sent it.
-->

## `run_classifier()` in 15 lines

```cpp
static float window[EI_CLASSIFIER_DSP_INPUT_FRAME_SIZE];   // 200 × 3, interleaved

signal_t signal;
numpy::signal_from_buffer(window,
    EI_CLASSIFIER_DSP_INPUT_FRAME_SIZE, &signal);

ei_impulse_result_t result;
uint32_t t0 = micros();
EI_IMPULSE_ERROR err = run_classifier(&signal, &result, false);
uint32_t dt = micros() - t0;                                // ← latency, for the scoreboard

for (size_t i = 0; i < EI_CLASSIFIER_LABEL_COUNT; i++)
    Serial.printf("%s: %.3f\n", result.classification[i].label,
                                result.classification[i].value);
```

---

<!--
On-device architecture — same for all three models. The double-buffer figure is
from the old NN assignment; the concept ports 1:1, only the sensor and board
names changed. 50% overlap doubles the prediction rate for free.
-->

## The canonical on-device ML loop

Every embedded ML application has the same skeleton — here as keyword spotting:

![w:700](assets/reddi/4-5-2-kws-components.png)

<sub>Figure: TinyML on edX (HarvardX), V.J. Reddi et al. — used with permission</sub>

<!--
The HarvardX keyword-spotting architecture — swap microphone for accelerometer, TFLite-Micro for our EI/emlearn model, LEDs stay LEDs, and it IS our fan firmware: provider → feature extractor → model → recognizer (smoothing/thresholds) → responder. Naming the five roles now makes the next slide's double-buffer diagram read as "the provider role, done right" instead of new material.
-->

---

## Firmware architecture — double buffering

![w:900](../brightspace-export/assignment/i1b47319e-6d63-4031-8466-8179c421eecf/NN%20model%20on%20device.png)
<!-- TODO: figure says Photon 2 / ADXL343 — redraw with RAK4631 / LIS3DH before course. Concept unchanged. -->

- Fill buffer B while computing features + inference on buffer A, then swap
- 50 % overlap → a prediction every second instead of every two
- A tiny state machine (`SAMPLING → INFER → REPORT`) keeps it honest

---

<!--
Measurement methodology for the shoot-out. Flash/RAM from the PlatformIO build
summary (delta vs an empty baseline build), latency with micros(), accuracy
from the held-out test set (Studio's model testing page, or the notebook).
-->

## Measuring the contenders

| Metric | How |
|---|---|
| Accuracy | held-out test set (Studio *Model testing* / notebook confusion matrix) |
| Flash | PlatformIO build summary — model build minus empty baseline build |
| RAM (static) | build summary + `EI_CLASSIFIER_*` estimates in `model_metadata.h` |
| Latency | `micros()` around inference, median of ≥ 20 runs |

```
RAM:   [====      ]  38.2% (used 100 kB from 256 kB)
Flash: [===       ]  31.0% (used 316 kB from 1 MB)      ← write these down
```

---

<!--
The scoreboard — the worksheet they hand in. Numbers below are placeholders
demonstrating the *expected order of magnitude*, not answers.
-->

## The shoot-out scoreboard

| Model | Accuracy | Flash Δ | RAM Δ | Latency |
|---|---|---|---|---|
| RF (emlearn, float) | ____ % | ____ kB | ____ kB | ____ µs |
| Dense NN (EI, float32) | ____ % | ____ kB | ____ kB | ____ ms |
| 1D-CNN (EI, float32) | ____ % | ____ kB | ____ kB | ____ ms |

Typical order of magnitude: RF tens of µs / a few kB · dense NN ~ms · CNN several ms + tens of kB RAM.

**Fill it in during the lab — this worksheet is the module deliverable.**

---

<!--
The payoff of the prediction slide. When the RF confusion matrices come in,
blocked↔normal confusion should be visible in most teams' baseline — exactly
what Module 5 predicted, because blocked's signature (RPM shift) is invisible
to time-domain statistics. Then hand them the fix they already own: the band
energies from their own Module 5 C code. Start with one well-chosen axis
(13 → 18 features) to keep it a 20-minute change; all three axes (13 → 28) for
the thorough. This is the documented extension of exercise 7.1 — fast teams do
it in the lab, everyone should hear the punchline: the model didn't get
smarter, the FEATURES did.
-->

## The reveal — and the fix

- Baseline RF confusion matrix: **`blocked` ↔ `normal`** — was that your prediction?
- Why: `blocked`'s signature is an **RPM shift** — a frequency feature; time-domain stats never stood a chance
- **The fix you already own:** append the 5 **band energies** from your Module 5 feature code
  (one axis first: 13 → 18 features) → retrain → convert → redeploy
- Watch `blocked` separate — *documented extension in exercise 7.1*

> Same forest, same data — better **features**. Tuesday's lesson, now in production.

---

<!--
Rules of thumb — what to tell a colleague who asks "which model should I use?"
Also flag what all three have in common: they only know the classes we taught
them. Perfect cliffhanger for Module 8.
-->

## What usually wins, and why

- **Features + RF**: best accuracy-per-byte on small tabular/vibration datasets; start here
- **Features + small NN**: worth it when class boundaries are smooth/combinatorial; needs scaling
- **CNN on raw**: pays off with *lots* of data, or when features are unknown (audio!)
- All three share a blind spot: they **only know the five states we taught them**

> A worn bearing you never recorded will be confidently classified as… something. Module 8 fixes this.

---

<!--
Exercise hand-off. Three tracks; teams of 2. Track A is mandatory, B/C at least
one of the two, ambitious teams do all three. Point to the exercises folder.
-->

## Exercise hand-off — Module 7 lab

`exercises/module7-models/`

1. **7.1 — RF via emlearn** (`rf-features/`): train on your fan features, convert, deploy with live LIS3DH sampling, LED + serial output *(mandatory)* — **extension:** add the Module 5 band energies (13 → 18 features), retrain, watch `blocked` separate
2. **7.2 — EI deploy** (`ei-deploy/`): dense-NN impulse → Arduino-library export → PlatformIO, `run_classifier` on the live window
3. **7.3 — CNN track**: second EI impulse on raw data; redeploy; compare
4. **Worksheet**: fill the scoreboard (`comparison-worksheet.md`) — accuracy / flash / RAM / latency per model

**Checkpoint (end of block):** live fan classification on serial + a completed scoreboard row for ≥ 2 models.

---

<!--
Buffer slide for wrap-up discussion. Collect scoreboard numbers from teams on
the whiteboard — the spread between teams is itself a teaching moment (data
quality > model choice).
-->

## Checkpoint & bridge

- Compare scoreboards across teams — why do identical models score differently? *(hint: it's the data)*
- Keep the EI project open: Module 8 adds an **anomaly block** next to your classifier
- Keep the PlatformIO project: Module 9 will re-deploy it **quantised**

**Next: Module 8 — what happens when the fan breaks in a way you never recorded?**
