# Module 6 Exercise — emlearn: sklearn → C header → RAK4631

Train a Random Forest on the XOR problem in scikit-learn, convert it to a single C header with **emlearn**, and run live classification on your RAK4631 over the serial monitor. Then fill in the framework-comparison worksheet.

The ML here is deliberately trivial — **the toolchain loop is the lesson**: this is exactly how Day 3's Random Forest on your fan features will reach the device.

⏱ Budget: ~60 min for parts 1–3, ~20 min for the worksheet.

Adapted from the earlier course's emlearn exercises and Jon Nordby's *Practical TinyML with emlearn* guest lecture (Aarhus 2026). emlearn docs: https://emlearn.readthedocs.io

## Prerequisites

- Python env with `scikit-learn`, `matplotlib`, `emlearn` (`pip install "emlearn==0.23.*"` — **pin the version** and use the same pin as setup-guide.md §4). The device-side runtime headers are vendored in `xor-device/lib/emlearn/` at **0.23.2**; keeping the generator on the same major.minor avoids skew between the header the model generator emits and the runtime that compiles it.
- Working PlatformIO + RAK4631 setup from Module 2.
- Optional for the laptop-compile detour: a host C compiler (`gcc`/`clang`).

## Part 1 — Train and convert (`xor-train/`)

```bash
cd xor-train
python train_xor.py
```

The script:

1. generates a noisy XOR dataset (2 features in [0,1], class = XOR of the halves) and plots it (`xor_data.png`),
2. **quantises the features to integers 0..255** (`FEATURE_SCALE`) — see the box below,
3. trains `RandomForestClassifier(n_estimators=10, max_depth=5)` — **expected accuracy ≈ 0.89** on the test split,
4. converts with `emlearn.convert(model)` and saves **`xor_model.h`**,
5. sanity-checks the converted model on the four XOR corners, and **exits non-zero if
   sklearn and the converted model disagree** — do not flash a model that fails this.

> **Why integers?** emlearn's tree runtime is *fixed-point*: `EmlTreesNode.value` is an
> `int16_t` (look in `eml_trees.h`). Features in [0,1] therefore cannot work — the split
> thresholds (~0.5) land in an integer field and truncate to **0**, every comparison
> `features[i] < 0` is false, and the model predicts a constant class. Scaling to
> 0..255 before training makes the thresholds honest integers (~104, ~7, ...). This is
> the same trick as the upstream emlearn XOR example, and it is a preview of Module 9:
> integer inference needs no FPU and costs less flash.
>
> Do **not** pass `method=`/`dtype=` to `convert()`. `dtype='float'` emits float
> literals into that `int16_t` table (`narrowing conversion` — the firmware will not
> build), and `dtype='int16'` with `method='inline'` emits `const int16 *features`,
> which is not a C type. Both bugs are present in emlearn 0.21 *and* 0.23; the default
> path is correct on both.

**Look inside `xor_model.h`** before moving on. It is readable C: each tree is a
nest of `if (features[i] < threshold)` — you can trace a prediction by hand.
This transparency is the whole point of emlearn.

Why XOR? It's the smallest problem that is *not linearly separable* — a
single threshold can't solve it, a forest of depth-2 trees can.

Copy the model **and the emlearn runtime headers** into the device project:

```bash
cp xor_model.h ../xor-device/include/
```

That is the only copy you need. The generated header does `#include <eml_trees.h>`,
and the emlearn runtime is **already vendored** in `xor-device/lib/emlearn/` —
`platformio.ini` adds `-I lib/emlearn` to the build flags.

> **Where do C headers come from in a Python package?** `pip install emlearn` ships
> emlearn's C runtime *inside* the Python package — `python -c "import emlearn;
> print(emlearn.includedir)"` prints the directory holding them. That is worth seeing
> once, because it is the whole train-in-Python/run-in-C idea in one path. We vendor
> the three headers the model actually needs (`eml_trees.h` → `eml_common.h` →
> `eml_log.h`, 14 KB) rather than have you copy that directory, because `includedir`
> is the package dir: copying it drags 43 headers **and 46 `.py` files** — 976 KB of
> Python — into a microcontroller project, and it pins the runtime to the version the
> generator was tested against instead of whatever your `pip` happens to hold.

> **Troubleshooting**
> - `ModuleNotFoundError: emlearn` — activate the course venv (`source ~/tinyml-env/bin/activate`).
> - Accuracy ~0.5 — you regenerated data without labels matching the plot; just rerun the script (fixed seed).

## Part 2 — Deploy (`xor-device/`)

```bash
cd xor-device
# make sure include/xor_model.h exists (Part 1)
pio run -t upload
pio device monitor        # 115200 baud
```

Type two numbers in [0,1] separated by space, press Enter. The firmware scales them by
`FEATURE_SCALE` (255) into the integers the model was trained on and prints both, so you
can see the quantisation happen. It does not echo what you type — start the monitor with
`pio device monitor --echo` to see your own input:

```
0.9 0.1                                          ← you type
in=(0.90, 0.10) = (230, 26) -> class 1 (XOR true)   latency=<x.xx> us (<n> cycles)
0.9 0.8                                          ← you type
in=(0.90, 0.80) = (230, 204) -> class 0 (XOR false)  latency=<x.xx> us (<n> cycles)
```

> **Why the latency field is trustworthy now.** `micros()` on this core falls back to
> the FreeRTOS tick (1024 Hz = 976.5625 µs steps) unless DWT is enabled — coarser than
> the thing being measured, so a single tree inference always printed `latency=0 us`.
> The firmware calls `dwt_timing_enable()` in `setup()`, giving `DWT->CYCCNT` timing at
> 15.6 ns. Cycles are printed alongside µs because cycles are the honest unit: they do
> not change if the clock does. If you ever see `latency=0.00 us`, DWT did not enable.

**`FEATURE_SCALE` in `src/main.cpp` must equal `FEATURE_SCALE` in `train_xor.py`.** The
thresholds baked into the model are in those units, so a mismatch silently moves every
decision boundary — the model still runs and still looks plausible.

- **Expected output:** the four corners `(0,0)→0, (0,1)→1, (1,0)→1, (1,1)→0`, and the green LED lit for class 1, blue for class 0.
- Note the latency — a 10-tree forest predicts in **tens of microseconds** on a 64 MHz M4F.
- Check the footprint: `pio run -t size` (or read the flash/RAM summary after build). Compare against a blink sketch — the model costs a few kB of flash and essentially zero RAM.

> **Troubleshooting**
> - `xor_model.h: No such file or directory` — you skipped the first `cp` in Part 1; the header is *generated*, not checked in.
> - `undefined reference to xor_model_predict` — your emlearn version generated a different function name; open `xor_model.h` and check the actual name (it is `<name>_predict`) — adjust the call in `src/main.cpp`.
> - `narrowing conversion of '4.08946991e-1f' from 'float' to 'int16_t'` (a wall of them) — the model was converted with `dtype='float'`. Remove the `method=`/`dtype=` arguments from `emlearn.convert()` and regenerate; see the box in Part 1.
> - `unknown type name 'int16'` — converted with `method='inline', dtype='int16'`; emlearn emits `int16` instead of `int16_t`. Same fix: use `emlearn.convert(model)` with no arguments.
> - Model always predicts the same class — the classic symptom of unscaled [0,1] features: every threshold truncated to 0. Check `FEATURE_SCALE` matches on both sides.
> - Build fails: `eml_trees.h: No such file or directory` — the vendored runtime in `xor-device/lib/emlearn/` is missing or `-I lib/emlearn` was removed from `build_flags` in `platformio.ini`. Restore with `git checkout xor-device/lib/emlearn`, or re-copy from `python -c "import emlearn; print(emlearn.includedir)"`.
> - No serial echo — the monitor sends on Enter; set *Send* mode / newline in your monitor, or use `pio device monitor --echo`.

## Part 3 — Experiments

1. **Latency vs model size:** retrain with `n_estimators=100, max_depth=10`, redeploy, compare latency and flash usage. Where does it stop being "free"?
2. **Circular dataset** (from the old course): `train_xor.py --circular` generates a ring-classification problem. How many trees / what depth does the forest need? What does the decision-boundary plot look like?
3. **`method='loadable'`:** reconvert and diff the two headers — inline = code, loadable = data tables + a generic tree-walker. Which is smaller for the 100-tree forest?

## Part 4 — Framework-comparison worksheet

Fill in **`framework-comparison.md`** using the frameworks' own documentation
(links inside). We reconcile the tables in the wrap-up — bring defensible
answers, not guesses.

## Deliverables

- `xor_model.h` deployed and the four corners classified correctly (screenshot of the monitor)
- latency + flash numbers for the 10-tree and 100-tree forests
- completed `framework-comparison.md`
