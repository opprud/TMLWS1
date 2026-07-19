# Module 9 — Optimisation: quantisation & pruning

Same models as yesterday's shoot-out — now smaller and faster, with the deltas measured. Three parts; (a) is the core, (b) and (c) parallelise well across a team.

| Part | What | Tooling |
|---|---|---|
| (a) | EI model as **int8 (EON)** vs **float32** on device | Edge Impulse + PlatformIO |
| (b) | **Magnitude pruning** of the dense fan model | Keras + `tensorflow_model_optimization` → [`notebooks/pruning_dense_model.ipynb`](notebooks/pruning_dense_model.ipynb) |
| (c) | **emlearn tree dtypes** int8/int16/int32 vs float | [`emlearn_dtype_compare.py`](emlearn_dtype_compare.py) + Module 7.1 firmware |

Add all results to your Module 7 worksheet — the optimised rows go under the float rows so the deltas stare back at you.

---

## Part (a) — EI int8 (EON) vs float32

### Steps

1. Open your Module 7/8 EI project → **Deployment** → *Arduino library*.
2. Under model optimisations, note the **estimates table** shown for:
   - *Quantized (int8)* + EON compiler **enabled**
   - *Unoptimized (float32)*
   Copy both columns into the table below **before** building. <!-- VERIFY: Studio labels — currently "TensorFlow Lite" vs "EON Compiler" toggle plus int8/float32 selector -->
3. Also record accuracy per version: **Model testing** page → the int8 model's test accuracy is shown when the quantized model is selected (calibration uses your training windows).
4. Build + download **both** libraries. Deploy each into your PlatformIO project from Exercise 7.2 (swap the `lib/<Name>_inferencing/` folder; `pio run -t clean` between builds so stale objects don't lie).
5. For each build, from the RAK4631 at 115200 baud, collect ≥ 20 inferences and note the median:

   ```cpp
   uint32_t t0 = micros();
   run_classifier(&signal, &result, false);
   uint32_t dt = micros() - t0;   // plus result.timing.dsp / .classification
   ```

6. Record flash/RAM from the PlatformIO build summary (same baseline-delta method as Module 7).

### Results table

| | float32 (Studio est.) | float32 (measured) | int8+EON (Studio est.) | int8+EON (measured) |
|---|---|---|---|---|
| Test accuracy | | n/a | | n/a |
| Latency (classifier) | ms | µs | ms | µs |
| RAM | kB | kB (build) | kB | kB (build) |
| Flash | kB | kB (build) | kB | kB (build) |

### Questions

1. How far off were Studio's estimates on your 64 MHz board (estimates assume a reference M4 @ 80 MHz)?
2. Where did int8 win the most — RAM, flash or latency? Explain each via the deck (bytes/param, activations, SIMD/memory traffic).
3. Did accuracy move at all? If yes, look at *which* classes got worse in the int8 confusion matrix.

---

## Part (b) — Pruning the dense fan model

Work through [`notebooks/pruning_dense_model.ipynb`](notebooks/pruning_dense_model.ipynb). It reads the same fan CSVs as part (c) — `../module7-models/rf-features/data/raw/`, created from your EI export with `ei_json_to_csv.py` (see part (c) step 1). It:

1. rebuilds/loads the Module 7 dense model (13 features → 8 → 16 → n_classes),
2. applies **magnitude pruning** with a `PolynomialDecay` schedule at final sparsities {0.5, 0.7, 0.8, 0.9},
3. plots **sparsity vs test accuracy**,
4. compares gzipped model sizes (the honest "does pruning shrink anything?" test),
5. discusses structured vs unstructured — and why the zeros don't make a dense MCU kernel faster.

> **VERIFY (before the course):** `tensorflow-model-optimization` requires the *legacy* Keras. With TensorFlow ≥ 2.16 / Keras 3 you must `pip install tf_keras` and set `TF_USE_LEGACY_KERAS=1` **before** importing TensorFlow, or pin `tensorflow<2.16`. tfmot has seen little maintenance since 2023 — re-test the notebook against the shipped Python environment.

Deliverable: the sparsity-vs-accuracy plot + one sentence: at what sparsity would *you* stop, and what did it actually buy?

---

## Part (c) — emlearn integer trees

Trees have no weights — quantising a forest means choosing the **dtype the feature thresholds are stored and compared in**. Your features must fit that range, so they get scaled to integers on the way in.

1. Run the comparison script (uses your Module 7 data + training code — it reads the CSVs in `../module7-models/rf-features/data/raw/`; if empty, convert your EI export first with `python ../module7-models/ei_json_to_csv.py <export>`, as in Module 7 Step 1):

   ```bash
   python emlearn_dtype_compare.py
   ```

   It trains one forest, converts it four ways (`float`, `int32_t`, `int16_t`, `int8_t`), reports header sizes and the laptop-side prediction agreement of each integer model vs the float model.

2. Pick `float` and one integer dtype and deploy both with the Exercise 7.1 firmware (swap `fan_model.h`, adjust the feature scaling as printed by the script), and compare:
   - flash (build summary),
   - latency (the `model ... us` figure on serial),
   - live behaviour on the fan.

### Questions

1. `int8` gives 256 distinct threshold levels. Look at your feature histograms — which features survive that, and which get crushed?
2. Why is the latency change here much smaller than the NN's float→int8 change? (Hint: what maths does a tree do per node?)
3. Flash: how much did the header shrink? Where does the saving come from (threshold storage)?

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| int8 build fails but float32 built fine | Clean build (`pio run -t clean`); make sure only **one** `<Name>_inferencing/` folder is in `lib/`. |
| int8 accuracy collapses (>5 % drop) | Check Model testing with the quantized model selected; if confirmed, your feature ranges are outlier-heavy — try re-recording the noisy class, or fall back to float32 for the DSP+NN and report it (that's a valid engineering result). |
| `ModuleNotFoundError: tensorflow_model_optimization` | `pip install tensorflow-model-optimization` (and see the VERIFY note about `tf_keras`). |
| tfmot import crashes with Keras 3 errors | `pip install tf_keras`, then `export TF_USE_LEGACY_KERAS=1` before starting Jupyter. |
| Integer emlearn model disagrees with float on many windows | Feature scaling mismatch — the integer models expect features multiplied by the scale factor the script printed; apply the same factor in `features.h` output before `fan_model_predict`. |

## Checkpoint (course finale)

Completed optimisation tables for (a) + at least one of (b)/(c), and your one-sentence shipping decision: **which model, which format, and why**.
