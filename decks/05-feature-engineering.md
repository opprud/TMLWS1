---
marp: true
theme: tinyml-clean
paginate: true
---

<!-- _class: title -->

# Module 5
# Feature Engineering

**From raw vibration windows to numbers a small model can love**
TinyML Course · Day 2

<!--
Module 4 gave everyone a labelled 5-class fan dataset. This module answers: what do we actually feed a model? We do the classic arc — time-domain statistics on WISDM (a known-good public dataset), then repeat on their own fan data, add the NEW spectral section (the old course explicitly skipped FFT features — we don't), and finally implement the chosen features in C on the RAK4631 with numerical validation against Python. Roughly 40% lecture, 60% lab.
-->

---

# Why features at all?

- A 2 s window = 200 samples × 3 axes = **600 raw numbers**
- Small models (logistic regression, random forest, small MLP) want **few, informative inputs**
- A feature = a *summary statistic* that compresses a window into one number
  - `std(x)` ≈ "how much does it shake?"
  - `zero_crossings(x)` ≈ "how fast does it oscillate?"
- Good features = smaller model = less RAM/flash/latency on the MCU
- Deep learning can learn features from raw data (Day 3, CNN) — at 10–100× the resource cost

<!--
Frame the engineering trade: handcrafted features + tiny classical model vs raw data + CNN. Jon Nordby's Module 6 deck cites literature (Elsts & McConville 2021): trees on features match deep learning on HAR at 10-100x less resources. On a 256 KB nRF52840 that's not an academic point. Also: features are interpretable — "band energy at 1x RPM went up" is a maintenance report; CNN activation #4217 is not.
-->

---

# The pipeline position

```
sensor → [ window ] → [ FEATURES ] → [ model ] → class
          200×3 @ 2s     ~10-60 nums    RF / NN
```

- Same features must be computed **twice**, identically:
  - **Training** (Python, on the PC, on the whole dataset)
  - **Inference** (C, on the MCU, on the live window)
- Any mismatch = silent accuracy loss → this module ends with a **Python-vs-C validation**

<!--
This dual-implementation problem is THE recurring TinyML pain point (Nordby calls it the data-scientist/firmware-engineer gap). Plant the flag now: the last exercise today is a golden-sample test proving your C features match numpy to ~1e-5. Edge Impulse solves the same problem by generating both sides from one DSP block definition — that's part of what you pay their pricing model for (Module 6).
-->

---

# Windowing recap

- Slice the continuous stream into **fixed-length windows**; each window → 1 feature vector → 1 prediction
- **Window length**: long enough for several cycles of the phenomenon
  - Fan at ~25 Hz rotation → 2 s window = ~50 revolutions ✔
- **Overlap** (e.g. 50%): more training windows from the same data, smoother live predictions
- Label of a window = the label of its recording

![height:230](../brightspace-export/_ontent/ia06c79eb-a027-4977-b14c-99d49ee28fc5/image_20250106104312467.png)

<!-- Reused figure: raw WISDM accelerometer trace (HW-agnostic plot) from the old feature exercise. -->

<!--
The WISDM notebook uses 100-sample windows at 20 Hz (5 s) with 50-sample steps (50% overlap) — human gait is ~1-2 Hz so 5 s captures ~5-10 strides. Our fan spins at 25 Hz, so 2 s is generous. Rule of thumb: window >= 5-10 cycles of the slowest phenomenon you care about. Overlap caveat: overlapping windows are correlated — one more reason to split train/test by recording, never by window (Module 4 rule 2).
-->

---

# Time-domain features — the core six

For each axis (window $x_1..x_N$):

| Feature | Formula | Captures |
|---|---|---|
| mean | $\bar{x} = \frac{1}{N}\sum x_i$ | static orientation / gravity |
| std | $\sqrt{\frac{1}{N}\sum (x_i-\bar{x})^2}$ | vibration intensity |
| RMS | $\sqrt{\frac{1}{N}\sum x_i^2}$ | total energy (incl. DC) |
| min / max | — | extremes, impacts |
| zero crossings | # sign changes of $(x_i-\bar{x})$ | dominant frequency proxy |

<!--
Work one tiny example on the whiteboard: x = [1, -1, 1, -1] -> mean 0, std 1, RMS 1, ZC 3. Note the RMS/std relation: RMS² = mean² + std² (biased std) — so for zero-mean signals they coincide; for an axis carrying gravity they differ a lot. Zero crossings counted around the mean, not around zero, for exactly that reason. These six are what we'll implement in C — cheap, no sorting, no scipy.
-->

---

# The extended zoo (WISDM: 59 features)

Stage 1 statistical measures from the WISDM walkthrough — per axis:

- mean, std, **average absolute deviation**, min, max, max–min
- median, **median absolute deviation (MAD)**, **IQR**
- neg/pos counts, values-above-mean, **peak count**
- **skewness** (asymmetry), **kurtosis** (spikiness!)
- **energy** $\frac{1}{N}\sum x_i^2$, plus cross-axis: **average resultant** $\overline{\sqrt{x^2+y^2+z^2}}$, **SMA**

Stage 3: argmin/argmax indices. → 59 features total.

<!--
Straight from the data_exploration notebook (brightspace-export). Highlight kurtosis for our fan: impulsive scraping = heavy-tailed distribution = high kurtosis; smooth imbalance sinusoid = low (negative excess) kurtosis. That single feature nearly separates scrape from imbalance. Median/MAD/IQR are robust versions of mean/std — they cost a sort on the MCU, so we skip them in this module's streaming feature path; Module 7's batch path (one buffered window per inference) can afford the sort, and its baseline feature set does include MAD. Don't memorise the zoo; the workflow is: compute many cheaply in Python, let feature importance pick the few worth porting to C.
-->

---

# Case study: WISDM human-activity dataset

- 1.07 M accelerometer samples, 20 Hz, 36 users, 6 activities (Walking, Jogging, Up/Downstairs, Sitting, Standing)
- Same shape as our problem: 3-axis accel, multi-class, time-series
- Split **by user** (train: users 1–27, test: 28–36) — the "split along the generalisation axis" rule again

![height:260](../brightspace-export/_ontent/ia06c79eb-a027-4977-b14c-99d49ee28fc5/image_20250106104409116.png)

<!-- Reused figure: WISDM x-axis distribution histogram from the old exercise (HW-agnostic). -->

<!--
Why teach on WISDM before their own data? (1) it's big and known-good, so bugs are in your code, not your data; (2) results are comparable across participants; (3) the class imbalance and the messy raw txt file are realistic. The notebook (notebooks/01_wisdm_features.ipynb, adapted from the old course data_exploration) walks: clean -> EDA -> window -> 59 features -> logistic regression (~80% acc) -> random forest -> feature importance.
-->

---

# Does it work? Baseline classifier on features

- Logistic regression on 59 features, standardised → **~80 % accuracy** on unseen users
- Reading a **confusion matrix**: rows = true class, columns = predicted, diagonal = correct
- Confusion concentrates where physics says it should: Upstairs ↔ Downstairs ↔ Walking

![height:330](../brightspace-export/_ontent/ia06c79eb-a027-4977-b14c-99d49ee28fc5/image_20250106122238782.png)

<!-- Reused figure: WISDM confusion matrix from the old exercise. -->

<!--
First appearance of logistic regression, so one primer sentence before anything else: it's a weighted sum of the features squashed through a sigmoid/softmax into class probabilities — the simplest trainable classifier there is, which is exactly why we use it as the floor. A linear model scoring 80% on 6 classes is the proof that the features carry the information — logistic regression can't extract anything the features don't already expose. Take 30 seconds on reading the matrix itself (some saw it in the Module 1 notebook, don't assume it stuck): each row is the true class, each column what the model said, so the diagonal is correct and any bright off-diagonal block is a pair of classes the features don't separate. That reading skill matters for Day 3. Ask: which fan states do you predict will confuse? (blocked vs normal is the likely pair, from Module 4's sanity check.)
-->

---

# Random Forest in five minutes (1/2) — the decision tree

- A **decision tree** = a learned cascade of `if (feature < threshold)` splits
- Training = greedily picking, at each node, the split that best separates the classes
- Prediction = follow the branches to a leaf → class

```
if (y_std < 0.021)        → Sitting/Standing
else if (x_mad < 0.40)    → Walking
else if (z_energy > 12.0) → Jogging
...
```

No weights, no gradients — just comparisons on your features.

<!--
Five-minute primer, because we're about to *use* a random forest before Day 3 formally introduces it. A decision tree is the ML model embedded engineers already believe in: it literally compiles to if-statements (Module 6's emlearn does exactly that). Training is nothing mystical — at each node the algorithm tries candidate thresholds on candidate features and keeps the split that makes the child groups purest. The full mechanics, and why trees are the natural MCU model, come tomorrow in Module 7 — today we only need enough to trust the tool.
-->

---

# Random Forest in five minutes (2/2) — the forest

- One tree happily **memorises noise** — deep trees overfit
- A **random forest** = many trees, each trained on a *random subset* of samples **and** features → **majority vote**
- Many overfit-but-different trees average out to a robust ensemble
- **Feature importance falls out for free:** every split *uses* a feature and *measurably improves* class purity → sum each feature's contribution over all trees = a ranking

That free ranking is exactly what we use next.

<!--
The forest fixes the tree's overfitting by voting: each tree sees a bootstrap sample of the data and a random subset of features at each split, so their errors decorrelate and the majority vote is far more stable than any member. The payoff for THIS module is the last bullet — because training already recorded how much each feature improved the splits, importance ranking costs nothing extra. That's why RF is the standard screening tool even when the deployed model ends up being something else. Full treatment tomorrow, Module 7 (where RF is also a contender in the deployment shoot-out).
-->

---

# Feature importance — let the forest rank them

```python
rf = RandomForestClassifier(n_estimators=15)
rf.fit(X_train, y_train)
pd.DataFrame(rf.feature_importances_, index=X_train.columns) \
  .sort_values('importance', ascending=False).head(10)
```

WISDM result: `y_std`, `y_pos_count`, `y_mad`, `y_IQR`, `y_maxmin_diff`, `x_mad`, ...

- Retrain on **top-10 only**: 79 % → 71 % — 6× fewer features, modest drop
- argmin/argmax indices land at the bottom (importance < 0.003) — dead weight

<!--
The gold arc from the old notebook: 59 features -> RF importance -> top-10 -> retrain -> compare confusion matrices. Notes: (1) RF importance is a ranking heuristic, not truth — correlated features share importance (y_std/y_mad/y_IQR all measure spread and split the credit); (2) for MCU deployment the question is "cheapest subset that keeps accuracy", so also weigh compute cost: y_std is one pass, y_IQR needs a sort; (3) trees need NO feature scaling — one less thing to replicate in C (the emlearn RF path in Module 7 exploits this).
-->

---

# Feature selection for the MCU

Aim for **~4 time-domain features per axis + band energies** (next section).
Screen candidates with three filters:

1. **Importance** — does the model care? (RF ranking)
2. **Cost** — single pass O(N)? needs sort? needs FFT?
3. **Redundancy** — std vs MAD vs IQR: pick *one* spread measure

For the fan lab, a strong starter set:

`std`, `RMS`, `zero-crossings`, `kurtosis` (time) + `band energies` (frequency, next)

<!--
This is the design decision each participant makes in the exercise: their own top-N list, justified in one sentence each. The bridging question from the old "Calculate features on our own dataset" exercise applies verbatim: how would you implement each chosen feature in C? If the answer is "scipy.stats.skew", think again — you'll write it from the raw sums.
-->

---

# Where time-domain features fail

Two fan states with **identical RMS**:

- `blocked`: fan spins *faster* (less air load), similar amplitude
- `normal`: nominal RPM

Amplitude statistics are **frequency-blind**. But:

- imbalance lives **at 1× RPM**
- blockage **moves** 1× RPM
- scrape spreads energy **across the spectrum**

→ We need the **frequency domain**. *(New material — the old course skipped this.)*

<!--
This is the motivation slide for the new spectral section. The old WISDM exercise literally said "skip the FFT features, stage 2" — for gait that was survivable; for rotating machinery the spectrum IS the diagnosis. Vibration analysts have worked in orders of RPM (1x, 2x, blade-pass) for 60 years; we're re-deriving their toolbox with an FFT and a for-loop.
-->

---

# FFT in five minutes

- DFT: any window = sum of sinusoids; FFT computes it in $O(N\log N)$
- Input: $N$ real samples at $f_s$ → output: $N/2$ complex **bins**
- Bin $k$ ↔ frequency $k \cdot f_s / N$ — resolution $= f_s/N$
  - 256 samples @ 100 Hz → **0.39 Hz/bin**, bins 0–50 Hz
- Magnitude $|X_k|$ = "how much of frequency $k$", phase usually discarded
- Multiply by a **window function** (Hann) first to reduce spectral leakage

```python
import numpy as np
mag = np.abs(np.fft.rfft(x * np.hanning(len(x)))) / len(x)
freqs = np.fft.rfftfreq(len(x), d=1/fs)
```

<!--
Keep the math light — engineers here have seen FFTs, they need the bookkeeping refreshed: bin index to Hz conversion, rfft returning N/2+1 bins, DC in bin 0 (that's your mean — drop or keep consciously). Leakage demo idea in the notebook: FFT of a 25.2 Hz sine with/without Hann window. On-device we'll use 256-point FFT on the 200-sample window zero-padded to 256 (or record 2.56 s windows — the exercise uses 256 samples directly).
-->

---

# Reading the fan spectrum

- **1× RPM fundamental**: fan at 1500 RPM → 25 Hz peak
- **Harmonics**: 2× (50 Hz — at our Nyquist edge!), 3×...
- **Blade-pass**: blades × 1× (7 × 25 = 175 Hz) — *aliased/invisible at 100 Hz sampling*
- Expectations per state:

| State | Spectrum |
|---|---|
| normal | modest 1× peak + low broadband |
| imbalance | **big 1× peak** |
| blocked | 1× peak **shifted up** in frequency |
| scrape | raised **broadband** floor, many harmonics |
| off | flat noise floor |

<!--
Everyone computes their own fan's spectrum in the notebook and must find the fundamental and check it against the RPM metadata from Module 4 (datasheet RPM / 60). That closing-the-loop moment — "my fan says 22.8 Hz, the datasheet says 1350 RPM = 22.5 Hz" — is the best 5 minutes of the day. Be honest about the aliasing: any true content above 50 Hz folds back; the LIS3DH has no analog anti-aliasing filter tuned to our rate, so strong blade-pass could alias into band. VERIFY in the field: if a mysterious stable peak appears, compute fold-back candidates.
-->

---

# Spectral features: band energy

Cheapest useful spectral feature — sum magnitudes over frequency bands:

$$ E_{band} = \sum_{k \in band} |X_k|^2 $$

- Our layout at $f_s$=100 Hz, N=256: **5 bands × 10 Hz** (0–10, 10–20, 20–30, 30–40, 40–50)
- Imbalance → energy piles into the band containing 1× RPM
- Blockage → energy *moves between* neighbouring bands
- Scrape → all bands rise
- Alternatives: spectral peak (argmax bin → Hz), spectral centroid, peak/total ratio

<!--
Band energy is robust to small RPM drift (unlike tracking the exact peak bin), trivially cheap after the FFT, and gives features with intuitive names ("energy 20-30 Hz"). Five bands x 3 axes = 15 spectral features. Optionally drop bin 0 (DC = gravity) before banding — the exercise code does. This mirrors exactly what Edge Impulse's Spectral Analysis block produces (next slide), so participants can cross-check numbers.
-->

---

# Aside: this is what EI's Spectral Analysis block does

- Module 4's feature explorer ran: filter → FFT → spectral power in bins + a few statistics
- Same maths, generated for you — plus auto-tuned parameters
- After today you can read the EI DSP block config and know **exactly** what each number is
- ...and you could replace it with your own C code (Module 6/7: exactly that trade-off)

<!--
Demystification moment: open the EI Spectral Features page for the fan project live and map each parameter (frame length, FFT size, noise floor) to what we just derived. This turns EI from magic into a convenience — which is the honest framing for the Module 6 framework comparison.
-->

---

# 🧪 Lab track A — features in Python (~45 min)

**`exercises/module5-features/notebooks/`**

- `01_wisdm_features.ipynb`: the reference walkthrough (59 features → RF → top-10)
- `02_fan_features.ipynb`: **your own fan data** — spectra, band energies, per-class boxplots
- Verify: does the 1×-RPM peak match the RPM you wrote in the metadata?
- **Done when:** you can name the 3 most important features for YOUR dataset

<!--
Notebook track first, while the theory is fresh. The RPM-verification moment is the payoff — the spectrum peak lining up with the metadata they recorded yesterday closes the loop between physics and features. The C track follows after the implementation slides.
-->

---

# Now in C — the implementation pattern

```c
// features.h — one pass, no malloc, no libc beyond sqrtf
typedef struct {
    float mean, std, rms, min, max;
    int   zero_crossings;
} time_features_t;

void time_features_compute(const float *x, int n, time_features_t *out);
```

- Accumulate `sum`, `sum_sq`, `min`, `max` in **one loop**
- `std = sqrtf(sum_sq/n - mean*mean)` — population std, matches `numpy.std` default
- Zero crossings: count sign changes of `x[i] - mean` (second short loop)
- **No dynamic allocation** — everything static/stack, MCU-friendly

<!--
The one-pass variance formula (E[x²] − E[x]²) can lose precision for large offsets in float32 — fine for ±4 g accel data centred near 0-1 g, worth one sentence for the numerically inclined (Welford's algorithm is the robust alternative). The std convention trap is real and is the #1 validation failure: numpy.std divides by N (population), pandas .std() by N-1 (sample). Pick N and be consistent on both sides. The exercise validation script will catch it if you don't — by design.
-->

---

# FFT on the nRF52840 — CMSIS-DSP

- Cortex-M4**F**: hardware FPU + SIMD → ARM's **CMSIS-DSP** library is the native choice

```c
#include "arm_math.h"
arm_rfft_fast_instance_f32 S;
arm_rfft_fast_init_f32(&S, 256);
arm_rfft_fast_f32(&S, input, output, 0);   // output: interleaved re/im
arm_cmplx_mag_f32(output, mag, 128);       // -> 128 magnitude bins
```

- 256-point float FFT: well under a millisecond at 64 MHz
- CMSIS-DSP also has one-call stats: `arm_mean_f32`, `arm_rms_f32`, `arm_std_f32` — compare against your loop!

<!--
VERIFY (also flagged in the exercise): how CMSIS-DSP is linked in this PlatformIO + Adafruit nRF52 BSP setup. The BSP ships CMSIS headers, but the DSP library binary/sources may not be linked by default; the exercise platformio.ini pins lib_deps to a CMSIS-DSP Arduino library package and there's a fallback plain-C DFT (#define USE_NAIVE_DFT) so nobody is blocked in class. arm_rfft_fast_f32 output packing quirk: output[0]=DC real, output[1]=Nyquist real (packed), then re/im pairs — the exercise code handles it; mention or they'll wonder why bin 1 looks weird. Timing teaser: measure the FFT with micros() — leads into the CMSIS statistics functions from the old assignment (i4a720c49) with the same timing methodology.
-->

---

# Validation: Python vs C (golden-sample testing)

![height:270](../brightspace-export/_ontent/i54af4816-6d6b-487d-960e-f56840d20f5a/Feature%20compare1.png)

<!-- Reused figure: Python-vs-C feature comparison diagram from the old "Feature comparison" page (HW-agnostic diagram; mentions Photon in surrounding text only). -->

1. Export a real recorded window (one per class) to a **C array header**
2. Compute features **in C on the device**, print over serial
3. Compute features **in numpy on the same array**
4. Compare: `|py - c| / |py| < 1e-4` → ✅

<!--
This is the methodology slide — golden-sample testing, same idea Nordby recommends for whole-pipeline validation (CSV in -> features out, on PC and on device) and the same idea the old feature_compare kit implemented. Why device and not just gcc-on-laptop? Same C code, but float behaviour, libm and compiler differ — testing on target catches the last class of surprises. The exercise ships validate_features.py which automates step 3-4 by parsing the device's serial output.
-->

---

# Timing your features

```c
uint32_t t0 = micros();
time_features_compute(win_x, N, &fx);
uint32_t dt = micros() - t0;
Serial.printf("time features: %lu us\n", dt);
```

- Typical (64 MHz M4F, N=256, per axis): stats ≈ tens of µs, FFT ≈ hundreds of µs
- Compare: window is 2 000 000 µs long → feature cost is **≈ 0.1 %** duty cycle
- This headroom is *the* TinyML power story: compute briefly, sleep long

<!--
Numbers above are order-of-magnitude expectations, not measurements — participants produce the real numbers in the exercise (and it's deliberately satisfying). Connect to Nordby's energy slide in Module 6: active burst + long sleep is why on-device beats streaming. If someone's stats loop takes milliseconds, check they compiled with optimisation (PlatformIO default -Os is fine) and aren't printf-ing inside the loop.
-->

---

# 🧪 Lab track B — features in C (~75 min)

**`exercises/module5-features/features-c/`**
*(track A — the notebooks — ran after the spectral section)*

1. Implement mean/std/RMS/min/max/ZC + FFT band energy on the RAK4631
2. Validate: `python validate_features.py --port /dev/ttyACM0` — **golden windows must PASS**
3. Report timing per feature (`micros()`)

**Done when:** Python and C agree to 6 decimals on the golden window.

<!--
Track A step 2's data path: EI Studio -> Data acquisition -> export (or Dashboard -> export). EI exports accelerometer samples as CBOR/JSON per sample plus CSV option; the notebook shows a loader for the JSON structure and a fallback CSV path — participants should not burn time reverse-engineering the format. Track B is scaffolded: features.h API given, function bodies are TODO with the reference implementation available in the solutions branch/folder for instructors.
-->

---

# Module 5 checkpoint

- ✅ You can name, compute and *choose* time-domain features — in numpy and in C
- ✅ You found your fan's rotation frequency in its own spectrum
- ✅ Band energies separate states that RMS alone cannot
- ✅ Your C features match Python to < 10⁻⁴ relative error — **validated, not hoped**
- ✅ You know the compute cost of every feature you plan to deploy

**Next (Module 6):** frameworks — who turns these features into a deployed model, and what it costs you in licence, footprint and lock-in.

<!--
Wrap by connecting forward: Module 6's emlearn XOR is deliberately tiny so the framework mechanics are visible; Day 3 Module 7 plugs TODAY's validated feature code in front of a random forest trained on TODAY's dataset. Everything is now on the table for the full chain.
-->
