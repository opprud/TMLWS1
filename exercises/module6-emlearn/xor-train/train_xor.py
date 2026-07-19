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
    fig, ax = plt.subplots(figsize=(5, 5))
    xx, yy = np.meshgrid(np.linspace(0, 1, 200), np.linspace(0, 1, 200))
    zz = model.predict(np.c_[xx.ravel(), yy.ravel()]).reshape(xx.shape)
    ax.contourf(xx, yy, zz, alpha=0.2, levels=1, cmap="coolwarm")
    ax.scatter(X[:, 0], X[:, 1], c=y, cmap="coolwarm", s=12, edgecolors="k", linewidths=0.2)
    ax.set_xlabel("feature 0")
    ax.set_ylabel("feature 1")
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
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=1)

    # Keep the model small ON PURPOSE — flash scales ~ trees * 2^depth.
    model = RandomForestClassifier(n_estimators=args.estimators,
                                   max_depth=args.depth, random_state=1)
    model.fit(X_train, y_train)
    acc = accuracy_score(y_test, model.predict(X_test))
    print(f"test accuracy: {acc:.3f}   (trees={args.estimators}, depth={args.depth})")

    plot_dataset(X, y, model, "xor_data.png")

    # ---- convert to C ------------------------------------------------------
    # method='inline' generates if/else trees; method='loadable' generates
    # data tables + a generic tree-walker. Either way, recent emlearn versions
    # #include <eml_trees.h> from the generated header, so the emlearn include
    # dir (`python -c "import emlearn; print(emlearn.includedir)"`) must be
    # copied into the device project -> see README Part 1 / platformio.ini.
    cmodel = emlearn.convert(model, method="inline")
    cmodel.save(file="xor_model.h", name="xor_model")
    print("wrote xor_model.h  ->  cp xor_model.h ../xor-device/include/")

    # ---- sanity check the CONVERTED model on the four corners --------------
    corners = np.array([[0.1, 0.1], [0.1, 0.9], [0.9, 0.1], [0.9, 0.9]])
    print("\ncorner check (sklearn vs converted):")
    sk = model.predict(corners)
    try:
        em = cmodel.predict(corners)  # emlearn evaluates the generated C-equivalent
    except Exception as exc:  # VERIFY: cmodel.predict availability varies by emlearn version
        em = ["n/a"] * 4
        print(f"  (converted-model predict unavailable in this emlearn version: {exc})")
    for c, a, b in zip(corners, sk, em):
        print(f"  in=({c[0]:.1f}, {c[1]:.1f})  sklearn={a}  emlearn={b}")

    # Rough footprint estimate before you even flash:
    try:
        from emlearn.evaluate.trees import model_size_bytes
        print(f"\nestimated model size: {model_size_bytes(model)} bytes")
    except Exception:
        pass  # VERIFY: emlearn.evaluate.trees API name/location across versions


if __name__ == "__main__":
    main()
