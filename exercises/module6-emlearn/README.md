# Module 6 Exercise — emlearn: sklearn → C header → RAK4631

Train a Random Forest on the XOR problem in scikit-learn, convert it to a single C header with **emlearn**, and run live classification on your RAK4631 over the serial monitor. Then fill in the framework-comparison worksheet.

The ML here is deliberately trivial — **the toolchain loop is the lesson**: this is exactly how Day 3's Random Forest on your fan features will reach the device.

⏱ Budget: ~60 min for parts 1–3, ~20 min for the worksheet.

Adapted from the earlier course's emlearn exercises and Jon Nordby's *Practical TinyML with emlearn* guest lecture (Aarhus 2026). emlearn docs: https://emlearn.readthedocs.io

## Prerequisites

- Python env with `scikit-learn`, `matplotlib`, `emlearn` (`pip install "emlearn==0.21.*"` <!-- VERIFY: current --> — **pin the version**, and use the same pin as setup-guide.md §4: the generated headers change between emlearn releases).
- Working PlatformIO + RAK4631 setup from Module 2.
- Optional for the laptop-compile detour: a host C compiler (`gcc`/`clang`).

## Part 1 — Train and convert (`xor-train/`)

```bash
cd xor-train
python train_xor.py
```

The script:

1. generates a noisy XOR dataset (2 features in [0,1], class = XOR of the halves) and plots it (`xor_data.png`),
2. trains `RandomForestClassifier(n_estimators=10, max_depth=5)` — **expected accuracy ≥ 0.97** on the test split,
3. converts with `emlearn.convert(model, method='inline')` and saves **`xor_model.h`**,
4. sanity-checks the converted model on the four XOR corners.

**Look inside `xor_model.h`** before moving on. It is readable C: each tree is a
nest of `if (features[i] < threshold)` — you can trace a prediction by hand.
This transparency is the whole point of emlearn.

Why XOR? It's the smallest problem that is *not linearly separable* — a
single threshold can't solve it, a forest of depth-2 trees can.

Copy the model **and the emlearn runtime headers** into the device project:

```bash
cp xor_model.h ../xor-device/include/
cp -r "$(python -c 'import emlearn; print(emlearn.includedir)')" ../xor-device/lib/emlearn
```

The second copy is required: recent emlearn versions `#include <eml_trees.h>`
from the generated header even with `method='inline'`. `platformio.ini`
already adds `-I lib/emlearn` to the build flags — this is the exact same
step Day 3's fan classifier (Module 7.1) uses.

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

Type two numbers in [0,1] separated by space, press Enter. The firmware does
not echo what you type — start the monitor with `pio device monitor --echo`
to see your own input:

```
0.9 0.1                                          ← you type
in=(0.90, 0.10) -> class 1 (XOR true)   latency=42 us
0.9 0.8                                          ← you type
in=(0.90, 0.80) -> class 0 (XOR false)  latency=41 us
```

- **Expected output:** the four corners `(0,0)→0, (0,1)→1, (1,0)→1, (1,1)→0`, and the green LED lit for class 1, blue for class 0.
- Note the latency — a 10-tree forest predicts in **tens of microseconds** on a 64 MHz M4F.
- Check the footprint: `pio run -t size` (or read the flash/RAM summary after build). Compare against a blink sketch — the model costs a few kB of flash and essentially zero RAM.

> **Troubleshooting**
> - `xor_model.h: No such file or directory` — you skipped the first `cp` in Part 1; the header is *generated*, not checked in.
> - `undefined reference to xor_model_predict` — your emlearn version generated a different function name; open `xor_model.h` and check the actual name (it is `<name>_predict` for `method='inline'`). `// VERIFY:` naming may differ across emlearn versions — adjust the call in `src/main.cpp`.
> - Build fails: `eml_trees.h: No such file or directory` — you skipped the second `cp` in Part 1: copy the emlearn include dir into `xor-device/lib/emlearn` (recent emlearn versions need it even with `method='inline'`), and check `-I lib/emlearn` is in `build_flags` in `platformio.ini`.
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
