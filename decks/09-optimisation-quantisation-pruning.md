---
marp: true
theme: tinyml-clean
paginate: true
---

<!--
Final module. Participants have float32 models running on the RAK4631 (Module
7) with an anomaly gate (Module 8). Now we shrink them and measure the deltas
with the same scoreboard discipline. Content sources: efficiency-metrics
section of the Intro-to-NN deck, the Fraunhofer AIfES Q7 workshop, emlearn
tree dtypes, plus a new pruning section. Ends with the course wrap-up.
Timing: ~55 min slides, then lab, then wrap-up discussion.
-->

<!-- _class: title -->

# Module 9
# Optimisation

**Quantisation & pruning: same model, fewer bytes, fewer cycles**
TinyML Course · Day 3

---

<!--
Motivation with our actual budget. 256 KB RAM / 1 MB flash sounds roomy until
you list the tenants. Battery: on a coin cell or energy harvester, every ms of
active CPU time is energy; radio transmission costs even more — recall Nordby's
cattle collar: computing on-device used 50× less power than streaming raw data.
-->

## Why optimise? Our budget, honestly

nRF52840: **256 KB RAM · 1 MB flash · 64 MHz Cortex-M4F**

Already living there: Arduino BSP + SoftDevice, serial stack, your DSP code, double buffers, the EI SDK…

- **Memory:** CNN activations + float32 weights eat RAM fast
- **Speed:** shorter inference → higher sample duty cycle, or more sleep
- **Energy:** sleep is the whole business case — compute beats transmit by ~50× (cattle-collar case, Module 6)

Optimisation is not polish. On batteries, it is the product.

---

<!--
Recap the four metric families from the Intro-to-NN deck (Day 1) — now they all
become knobs we can turn. This frames the whole module: quantisation attacks
bytes-per-parameter, pruning attacks parameter count and MACs.
-->

## The four dials (Day 1 recap)

| Model size | Memory | Compute | Performance |
|---|---|---|---|
| # parameters | peak activations | MACs / FLOPs | latency (ms) |
| model bytes | RAM at inference | ops count | energy / inference |
| float32 / int8 | | | inferences / s |

- **Quantisation** → shrinks *bytes per value* (weights **and** activations)
- **Pruning** → shrinks *number of values* (parameters, and sometimes MACs)

---

<!--
Model size arithmetic from the NN deck: size = #params × bytes/param. Worked
for our own models. The dense fan model is tiny either way; the CNN and the EI
DSP+NN pipeline is where int8 starts to matter on flash — and activations on
RAM.
-->

## Model size = #params × bytes/param

| Format | Bytes/param | 1 M params | Our CNN (~5 k params) |
|---|---|---|---|
| float32 | 4 | 4 MB | ~19 kB |
| float16 | 2 | 2 MB | ~10 kB |
| **int8** | **1** | **1 MB** | **~5 kB** |

- Dense fan NN (~1 k params): fits anywhere — flash is not its problem
- But: EI deployment = model **+ DSP code + SDK**; and RAM, not flash, is usually the wall

---

<!--
Peak activations — the RAM story, straight from the NN deck example. Weights
live in flash; activations are born and die in RAM during inference. The
largest intermediate tensor sets the RAM high-water mark. int8 quarters it.
-->

## RAM is the scarcer resource

- **Weights → flash** (persistent, 1 MB, usually fine)
- **Activations → RAM** (volatile, 256 KB, contested)
- Peak activation = largest intermediate tensor during inference

Example (Day 1): `28×28×1 → Conv(8) → 28×28×8 → Conv(16) → 14×14×16`
peak = 6 272 values after Conv1 → **25 kB float32 vs 6.3 kB int8**

Same model, same accuracy target — **4× RAM back**, just by changing the number format.

---

<!--
MACs ≠ latency (NN deck) — but int8 helps latency through a second door: the
Cortex-M4 has SIMD instructions that process four int8 lanes per cycle, and
int8 halves/quarters memory traffic. This is why int8 is typically faster even
though the MAC count is unchanged.
-->

## Why int8 is also *faster* (MACs ≠ latency)

MAC count doesn't change when you quantise. Latency drops anyway:

- **Memory traffic** — 4× fewer bytes through the bus and caches
- **SIMD** — Cortex-M4 DSP instructions chew multiple 8/16-bit lanes per cycle (CMSIS-NN kernels)
- typical TinyML latency window: 10–500 ms on Cortex-M4 — int8 commonly lands 2–4× lower than float
  <!-- VERIFY: 2–4× is a typical published range; confirm with your own micros() numbers in the lab -->

The FPU makes float *viable* on the M4F — int8 makes it *cheap*.

---

<!--
The mechanics of affine quantisation — one slide of theory so the lab numbers
make sense. real = scale × (q - zero_point). Per-tensor or per-channel scales.
Emphasise: it's a lossy map; the question of the day is how lossy.
-->

## Quantisation mechanics in one slide

Map floats to 8-bit integers with an affine transform:

```
real_value ≈ scale × (int8_value − zero_point)
```

- `scale`, `zero_point` chosen so the observed value range fits into [−128, 127]
- Weights: ranges known after training → quantise directly (often per-channel)
- **Activations: ranges depend on input data** → need *calibration* with representative samples
- Rounding error ≈ uniform noise — small for well-conditioned layers, ugly for outlier-heavy ones

---

<!--
PTQ: the cheap path. Feed a representative dataset through the float model to
record activation ranges, then convert. This is exactly what EI does when you
pick int8/EON — Studio uses your training windows as the calibration set.
-->

## Post-training quantisation (PTQ)

1. Train in float32 as usual
2. Run a few hundred **representative windows** through the model, record activation ranges
3. Convert weights + activations to int8 with the calibrated scales

- No retraining, minutes of work
- Typical hit on small models: **≈ 0–2 % accuracy**
- Edge Impulse does this automatically — the *Quantized (int8)* deployment option, calibrated on your dataset

---

<!--
QAT: simulate quantisation during training so the network learns around the
rounding noise. Costs a retraining run; wins back most PTQ losses. Decision
rule: try PTQ first, reach for QAT only if the accuracy drop is unacceptable.
-->

## Quantisation-aware training (QAT)

- Insert **fake-quantise** ops during training — forward pass sees int8 rounding, backward pass trains through it
- The network learns weights that are robust to quantisation noise
- Costs: a (re)training run + framework support (`tfmot`, EI enterprise)

| | PTQ | QAT |
|---|---|---|
| Effort | minutes | retraining |
| Accuracy loss | small, sometimes ugly | usually negligible |
| When | **always try first** | only if PTQ hurts |

---

<!--
EON compiler: EI's second trick, orthogonal to quantisation. Instead of
shipping the TFLite-Micro interpreter + FlatBuffer model, EON compiles the
graph to direct C++ — no interpreter overhead, and Studio reports the RAM/ROM
savings. int8 + EON is the default recommendation.
-->

## Edge Impulse EON compiler

Two independent switches at deployment time:

| | float32 | int8 (quantised) |
|---|---|---|
| **TFLite-Micro** | baseline | smaller |
| **EON compiled** | smaller RAM/ROM | **smallest** |

- EON = model graph compiled to direct C++ instead of interpreted FlatBuffer
- EI's published claim: same accuracy, up to ~25–55 % less RAM / ~35 % less flash vs TFLM
  <!-- VERIFY: EI's current published EON savings figures -->
- Studio shows **estimated RAM / flash / latency per option** before you build — read them, then verify with `micros()`

---

<!--
Show where to read the numbers in Studio (Deployment page shows a comparison
card per option). The lab worksheet mirrors exactly these fields, plus the
on-device measurements. TODO: add a fresh screenshot of the deployment page
with the fan project.
-->

## Studio tells you the price up front

Deployment page, per option:

```
                 Quantized (int8)      Unoptimized (float32)
Latency          ~ __ ms               ~ __ ms
RAM              ~ __ kB               ~ __ kB
Flash            ~ __ kB               ~ __ kB
Accuracy         __ % (model testing)  __ %
```

<!-- TODO: insert fresh screenshot of EI Deployment page (fan project) — none exists in brightspace-export; the 2026-05-14 screenshots cover impulse design & live testing only. -->

Estimates are for a reference M4 @ 80 MHz — *your* 64 MHz numbers come from `micros()` in the lab.

---

<!--
Trees quantise differently: emlearn converts the feature/threshold values to
integer dtypes; there are no weights in the NN sense. dtype choice int8/16/32
trades threshold resolution vs flash. Also mention inline vs loadable inference
modes from the Nordby deck.
-->

## 🧪 Lab part (a) starts now — EI int8 vs float32 (~15 min to queue)

**`exercises/module9-optimisation/README.md`** → part (a)

- Redeploy the Module 7 EI model **twice**: EON int8 and float32
- Note Studio's flash/RAM/latency estimates for both — the lab measures reality
- **Done when:** both builds are queued/downloaded

<!--
Part (a) queues now for the same pipelining reason as Module 7 — EI builds take server minutes. The comparison table gets filled during the lab with on-device micros() numbers next to Studio's estimates; the deltas are usually small and that credibility check is the point.
-->

---

## Quantising trees — emlearn dtypes

```python
cmodel = emlearn.convert(clf, method='inline', dtype='int16_t')
cmodel.save(file='fan_model_i16.h', name='fan_model')
```

- Trees have **no weights** — only feature *thresholds*. `dtype` sets the type your features are compared in: `float`, `int32_t`, `int16_t`, `int8_t`
- Smaller dtype → smaller flash, cheaper compares — but your features must **fit the range** (scale them to integers first!)
- `int8` means 256 distinct feature levels — check your feature histograms before choosing
- Inference itself was already multiplication-free — trees start where NNs end up

---

<!--
AIfES Q7 aside — connect to the Fraunhofer workshop material from Module 6.
Their Task 2 ships the same Iris FNN as f32 and Q7 headers; Q7 = fixed-point
int8 with power-of-two scaling. If teams did the AIfES track, they can rerun
Task 2 on the RAK4631 as a bonus.
-->

## 🧪 Lab part (c) — emlearn dtype ladder (~10 min)

**`exercises/module9-optimisation/emlearn_dtype_compare.py`**

- Convert the Module 7 forest as float / int32 / int16 / int8
- Compare header size + prediction agreement vs float
- **Done when:** you know which dtype your fan forest can afford

<!--
Ten-minute interlude that fits here because the mechanics were just taught. Integer trees usually agree 100% with float on well-separated classes — when they don't, the feature scaling note in the script explains the fix.
-->

---

## Aside: AIfES Q7 (from the Fraunhofer workshop)

- AIfES supports **Q7** (int8 fixed-point) inference — workshop Task 2 ships the same network as `aifes_f32_fnn.h` *and* `aifes_q7_fnn.h`
- Benchmarks from the workshop deck: vs TFLite-Micro, AIfES measured ~2× faster and up to ~4× less memory on small FNNs
- The workshop projects already target nRF52840 (`nano33ble`) — they build for the RAK4631 with a one-line board change
- **Bonus lab:** run f32 vs Q7 side by side, `micros()` both

---

<!--
NEW SECTION: pruning. Start with the observation that trained networks are
over-parameterised; many weights are near zero and contribute noise-level
signal. Magnitude pruning: rank by |w|, zero the smallest fraction, fine-tune,
repeat. Gradual schedules (PolynomialDecay) do this during training.
-->

## Pruning — most weights are freeloaders

Trained networks are over-parameterised: histogram the weights of your fan NN — a fat spike around zero.

![w:520](assets/reddi/5-6-7-dense-vs-sparse.png)

<sub>Figure: TinyML on edX (HarvardX), V.J. Reddi et al. — used with permission</sub>

**Magnitude pruning:**

1. Rank weights by `|w|`
2. Zero out the smallest X %
3. Fine-tune the survivors (the network heals)
4. Repeat / schedule until target **sparsity** (e.g. 80 %)

Small dense models often tolerate **50–80 % sparsity at < 1 % accuracy loss**. Your notebook will draw this curve for the fan model.

---

<!--
Structured vs unstructured — the slide that saves them from a classic trap.
Unstructured sparsity does not make standard MCU inference faster: the zeros
still occupy the dense weight array and still get multiplied, unless the
runtime has sparse kernels. Structured pruning removes whole neurons/channels
→ genuinely smaller dense matrices everywhere.
-->

## Structured vs unstructured — in pictures

![w:830](assets/reddi/5-6-7-structured-vs-unstructured.png)

<sub>Figure: TinyML on edX (HarvardX), V.J. Reddi et al. — used with permission</sub>

<!--
Left: unstructured pruning removes individual weights — the network keeps its shape, the weight matrices just fill with zeros. Right: structured pruning removes whole filters/neurons — the matrices genuinely shrink. This picture is the whole story of why only one of them speeds up an MCU.
-->

---

## Structured vs unstructured

| | Unstructured | Structured |
|---|---|---|
| What's removed | individual weights | whole neurons / channels / filters |
| Sparsity pattern | scattered zeros | smaller dense tensors |
| Accuracy per removed param | better | worse |
| Speedup on MCU | **none** without sparse kernels | **real** — fewer MACs, less RAM |
| Size win | only after compression (gzip/OTA) | immediate |

A dense matmul with 80 % zeros still executes 100 % of its MACs.

---

<!--
When does pruning pay? Honest answer for this class: (1) always for OTA /
storage via compression, (2) for real speed/RAM only when structured — which
for tiny models is often better achieved by just training a smaller model.
The "did you try a smaller model first" question is the punchline.
-->

## When pruning pays (and when it doesn't)

**Pays:**

- Compressed storage & OTA updates — sparse weights gzip beautifully
- Structured pruning of over-sized layers (our CNN's 560→8 dense layer is a prime target)
- Combined with quantisation: prune → quantise compounds

**Doesn't:**

- Unstructured pruning + standard TFLM/EON kernels → same latency, same RAM
- When the honest fix is a smaller architecture — *always try that first* (remember the grid search: 3 filters beat 8)

---

<!--
The tfmot workflow they'll use in the notebook. Big VERIFY flag: tfmot has
historically lagged Keras 3 — with TF ≥ 2.16 you need the tf_keras legacy
package and TF_USE_LEGACY_KERAS=1. The notebook carries the same warning.
-->

## Pruning in Keras (`tensorflow_model_optimization`)

```python
import tensorflow_model_optimization as tfmot   # VERIFY: needs tf.keras (Keras 2);
                                                # with TF>=2.16 set TF_USE_LEGACY_KERAS=1
prune = tfmot.sparsity.keras.prune_low_magnitude
schedule = tfmot.sparsity.keras.PolynomialDecay(
    initial_sparsity=0.0, final_sparsity=0.8,
    begin_step=0, end_step=end_step)

pruned = prune(model, pruning_schedule=schedule)
pruned.compile(...)
pruned.fit(..., callbacks=[tfmot.sparsity.keras.UpdatePruningStep()])
final = tfmot.sparsity.keras.strip_pruning(pruned)   # remove the wrappers
```

Notebook: sweep final_sparsity ∈ {0.5, 0.7, 0.8, 0.9}, plot **sparsity vs accuracy**, compare gzipped sizes.

---

<!--
Put the whole toolbox in one picture, in the order you should apply it.
Architecture first (cheapest win), then PTQ, then QAT/pruning as needed.
-->

## 🧪 Lab part (b) — prune the dense model (~25 min)

**`exercises/module9-optimisation/notebooks/pruning_dense_model.ipynb`**

- Magnitude-prune the Module 7 dense NN: sparsity 0.5 → 0.9
- Plot sparsity vs accuracy; gzip the models — watch compression grow
- **Done when:** you can say where YOUR model's accuracy cliff is

<!--
Pruning lab immediately after the pruning content. Watch for the tfmot/Keras-version footgun flagged in the notebook (TF >= 2.16 needs tf_keras + the env var). The accuracy cliff lands differently per dataset — comparing cliffs across pairs is a good 2-minute wrap discussion.
-->

---

## The optimisation ladder

1. **Right-size the architecture** — smallest model that meets accuracy (Module 7 grid search)
2. **PTQ int8 + EON** — near-free 4× on weights & activations
3. **Structured pruning / smaller layers** — if RAM or latency still hurts
4. **QAT** — if and only if PTQ cost too much accuracy
5. Exotic (int4, distillation, sparse kernels) — beyond this course

Measure after every rung. `micros()` doesn't lie; estimates sometimes do.

---

<!--
Exercise hand-off. Three parts mirroring the deliverables; part (a) is the
core, (b) and (c) parallelise well across team members.
-->

## 🧪 Lab wrap — finish the measurements, fill the table

All three parts started at their checkpoints — now close them out:

1. **(a) int8 vs float32:** flash both builds, put `micros()` + real flash/RAM next to Studio's estimates
2. **(b) pruning:** finish the sparsity sweep, note YOUR accuracy cliff
3. **(c) dtypes:** pick the dtype your fan forest ships with

**Done when:** the optimisation table is complete + one sentence: *what would you ship, and why?*

---

<!--
Course wrap-up part 1: replay the full chain they built in three days. Every
box on this slide is something they implemented themselves — that's the
achievement to name explicitly.
-->

## Three days, one system — built by you

```
LIS3DH @ fan  →  your forwarder  →  labelled dataset (EI)
      →  features (Python ⇄ C, validated)  →  RF / NN / CNN (compared)
      →  deployed on RAK4631  →  anomaly-gated  →  quantised & measured
```

- Day 1: why TinyML, the hardware, first data
- Day 2: the fan rig, features, framework landscape
- Day 3: models in a shoot-out, unknown-fault detection, optimisation

You didn't follow a tutorial — you built the pipeline that tutorials are about.

---

<!--
Wrap-up part 2 — from PC fan to production condition monitoring. Map each
course element to the industrial version. Leave time for discussion: what
would each participant's product need beyond this?
-->

## From PC fan to production condition monitoring

| Course rig | Production (pumps…) |
|---|---|
| 120 mm fan, 5 fault states | real machines, unknown fault space → **anomaly-first** |
| RAK1904 taped to the frame | qualified industrial sensors, proper mounting |
| 20-min datasets | months of fleet data, per-unit baselines, re-baselining after service |
| serial + LED | LoRa/BLE alerts (the SX1262 is already on your board), fleet dashboards |
| accuracy on a test split | false-alarm cost vs missed-fault cost, drift monitoring, model updates OTA |

Same pipeline. Same maths. Bigger consequences.

---

<!--
Final slide. Practicalities: materials stay available, project inspiration list
from previous students, contact. Thank them.
-->

## Wrap-up

- All materials, code and solutions: course repo (decks + `exercises/`)
- Keep the kit — the forwarder, features and models are yours to reuse
- Inspiration: previous student projects (knock detector, drone-sound detection, bike-theft alarm, …)
- Questions later: morten@ece.au.dk

**Thanks — now go monitor some machines.**
