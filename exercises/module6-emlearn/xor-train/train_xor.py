#!/usr/bin/env python3
"""Module 6 — train a Random Forest on XOR (or a circular dataset) and convert
it to a C header with emlearn.

Usage:
    python train_xor.py                 # XOR dataset -> xor_model.h
    python train_xor.py --circular     # ring dataset (Part 3 experiment)
    python train_xor.py --estimators 100 --depth 10

Then: cp xor_model.h ../xor-device/include/
"""

import argparse

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

import emlearn

# Feature scale: the generators below produce values in [0, 1], which we quantise
# to integers 0..FEATURE_SCALE before training. 255 matches the upstream emlearn
# XOR example and gives 8-bit resolution — ample for a 2-D toy problem, and it
# keeps every threshold comfortably inside int16. THE DEVICE MUST USE THE SAME
# NUMBER (xor-device/src/main.cpp) or the thresholds mean nothing.
FEATURE_SCALE = 255


def make_xor(samples=500, noise=0.10, seed=42):
    """Noisy XOR: 2 features in [0,1], class = XOR of which half each lies in."""
    rng = np.random.RandomState(seed)
    X = rng.uniform(0, 1, size=(samples, 2))
    y = np.logical_xor(X[:, 0] > 0.5, X[:, 1] > 0.5).astype(int)
    X = X + rng.normal(0, noise, size=X.shape)  # smear the boundary a little
    return np.clip(X, 0, 1), y


def make_circular(radius=0.5, samples=500, seed=42):
    """Ring dataset from the old course exercise: class 1 inside the radius."""
    rng = np.random.RandomState(seed)
    angles = rng.uniform(0, 2 * np.pi, samples)
    radii = rng.uniform(0, 1, samples)
    X = np.column_stack((radii * np.cos(angles), radii * np.sin(angles)))
    X = (X + 1) / 2  # map to [0,1]^2 like the XOR set
    y = (radii < radius).astype(int)
    return X, y


def plot_dataset(X, y, model, fname):
    """Scatter + decision boundary."""
    # The model is trained on integers 0..FEATURE_SCALE, so the decision-boundary
    # grid has to live in the same units — meshing over [0,1] would ask the model
    # about a 1x1 corner of its input space and produce a solid-colour plot.
    fig, ax = plt.subplots(figsize=(5, 5))
    grid = np.linspace(0, FEATURE_SCALE, 200)
    xx, yy = np.meshgrid(grid, grid)
    zz = model.predict(np.c_[xx.ravel(), yy.ravel()].astype(np.int16)).reshape(xx.shape)
    ax.contourf(xx, yy, zz, alpha=0.2, levels=1, cmap="coolwarm")
    ax.scatter(X[:, 0], X[:, 1], c=y, cmap="coolwarm", s=12, edgecolors="k", linewidths=0.2)
    ax.set_xlabel(f"feature 0  (0..{FEATURE_SCALE})")
    ax.set_ylabel(f"feature 1  (0..{FEATURE_SCALE})")
    ax.set_title("data + RF decision boundary")
    fig.savefig(fname, dpi=120, bbox_inches="tight")
    print(f"wrote {fname}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--circular", action="store_true", help="ring dataset instead of XOR")
    ap.add_argument("--estimators", type=int, default=10)
    ap.add_argument("--depth", type=int, default=5)
    args = ap.parse_args()

    X, y = make_circular() if args.circular else make_xor()

    # ---- quantise the features to int16 -----------------------------------
    # emlearn's tree runtime is FIXED-POINT: EmlTreesNode.value is an int16_t
    # (see eml_trees.h). Feeding it features in [0, 1] does not work — the split
    # thresholds (~0.5) land inside an integer field and truncate to 0, so every
    # comparison `features[i] < 0` is false and the model predicts a constant
    # class. Scale to integers BEFORE training, exactly as the upstream XOR
    # example does, and the thresholds become honest integers (~104, ~7, ...).
    # The device must apply the identical scale — see xor-device/src/main.cpp.
    X = (X * FEATURE_SCALE).astype(np.int16)

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=1)

    # Keep the model small ON PURPOSE — flash scales ~ trees * 2^depth.
    model = RandomForestClassifier(n_estimators=args.estimators,
                                   max_depth=args.depth, random_state=1)
    model.fit(X_train, y_train)
    acc = accuracy_score(y_test, model.predict(X_test))
    print(f"test accuracy: {acc:.3f}   (trees={args.estimators}, depth={args.depth})")

    plot_dataset(X, y, model, "xor_data.png")

    # ---- convert to C ------------------------------------------------------
    # Call convert() with DEFAULTS, as the upstream XOR example does. Do not pass
    # method=/dtype= here:
    #   * dtype='float' emits float literals into the int16_t EmlTreesNode table
    #     -> "narrowing conversion from float to int16_t" and the device build
    #     fails outright (and any threshold that did compile would truncate to 0);
    #   * dtype='int16' with method='inline' emits `const int16 *features` —
    #     `int16` is not a C type and emlearn typedefs it nowhere, so the header
    #     does not compile either. Both bugs are present in emlearn 0.21 and 0.23.
    # The default path emits an int16_t node table plus a correctly-typed
    # `int32_t xor_model_predict(const int16_t *, int32_t)`.
    #
    # The generated header #includes <eml_trees.h>, so the emlearn include dir
    # (`python -c "import emlearn; print(emlearn.includedir)"`) must be copied
    # into the device project -> see README Part 1 / platformio.ini.
    cmodel = emlearn.convert(model)
    cmodel.save(file="xor_model.h", name="xor_model")
    print("wrote xor_model.h  ->  cp xor_model.h ../xor-device/include/")

    # ---- sanity check the CONVERTED model on the four corners --------------
    # Corners are scaled the same way the training data was — this is the check
    # that catches a scale mismatch between here and the firmware.
    corners = (np.array([[0.1, 0.1], [0.1, 0.9], [0.9, 0.1], [0.9, 0.9]])
               * FEATURE_SCALE).astype(np.int16)
    print("\ncorner check (sklearn vs converted):")
    sk = model.predict(corners)
    try:
        em = cmodel.predict(corners)  # emlearn compiles + runs the generated C
    except Exception as exc:
        em = ["n/a"] * 4
        print(f"  (converted-model predict unavailable in this emlearn version: {exc})")
    ok = all(a == b for a, b in zip(sk, em)) if "n/a" not in em else None
    for c, a, b in zip(corners, sk, em):
        print(f"  in=({c[0]:4d}, {c[1]:4d})  sklearn={a}  emlearn={b}")
    if ok is False:
        raise SystemExit("\nFAIL: converted model disagrees with sklearn — do not flash this.")
    if ok:
        print("  all four agree ✔")

    # Rough footprint estimate before you even flash:
    try:
        from emlearn.evaluate.trees import model_size_bytes
        print(f"\nestimated model size: {model_size_bytes(model)} bytes")
    except Exception:
        pass  # VERIFY: emlearn.evaluate.trees API name/location across versions


if __name__ == "__main__":
    main()
