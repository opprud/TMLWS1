#!/usr/bin/env python3
"""
Module 9(c) - emlearn tree dtype comparison.

Trains the Module 7 Random Forest once, converts it with dtype float / int32 /
int16 / int8, and reports:
  - generated header size (proxy for flash cost of threshold storage)
  - prediction agreement of each integer model vs the float model on the test set

Integer trees compare *integer* feature values, so features are scaled by a
fixed factor before conversion and the SAME factor must be applied in C before
calling fan_model_predict(). The factor used here is printed at the end.

Outputs go to ./out_dtypes/fan_model_<dtype>.h - copy the one you deploy into
../module7-models/rf-features/platformio/src/fan_model.h (and scale features!).

VERIFY: emlearn dtype/convert API - emlearn.convert(clf, method='inline',
dtype='int16_t') per the emlearn tree-based-models docs; re-check against the
installed emlearn version before the course.
"""

import os
import sys

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split

import emlearn

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                "..", "module7-models", "rf-features")))
from train_rf import load_windows  # noqa: E402

DATA_DIR = os.path.join(os.path.dirname(__file__),
                        "..", "module7-models", "rf-features", "data", "raw")
OUT_DIR = os.path.join(os.path.dirname(__file__), "out_dtypes")

# Feature scale factor for integer models: features (in m/s^2-ish units, small
# floats) are multiplied by this before training the integer-converted model
# is *not* needed -- emlearn quantises thresholds; but int8 only spans -128..127
# so we pre-scale features into a range that survives integer truncation.
FEATURE_SCALE = {"float": 1.0, "int32_t": 1000.0, "int16_t": 1000.0, "int8_t": 10.0}


def main():
    X_raw, X, y, groups, _ = load_windows(DATA_DIR)
    labels = sorted(np.unique(y))
    y_int = np.array([labels.index(v) for v in y])
    Xtr, Xte, ytr, yte = train_test_split(X, y_int, test_size=0.25,
                                          random_state=42, stratify=y_int)

    os.makedirs(OUT_DIR, exist_ok=True)
    print(f"{'dtype':>10s} {'scale':>7s} {'header kB':>10s} {'test acc':>9s} {'agree vs float':>15s}")

    ref_pred = None
    for dtype in ["float", "int32_t", "int16_t", "int8_t"]:
        s = FEATURE_SCALE[dtype]
        clf = RandomForestClassifier(n_estimators=10, max_depth=8, random_state=42)
        clf.fit(Xtr * s, ytr)

        cmodel = emlearn.convert(clf, method="inline", dtype=dtype)
        path = os.path.join(OUT_DIR, f"fan_model_{dtype.rstrip('_t') if dtype != 'float' else 'float'}.h")
        cmodel.save(file=path, name="fan_model")
        size_kb = os.path.getsize(path) / 1024

        # Python-side check: sklearn prediction on (scaled, truncated) features
        # approximates what the integer C model sees.
        if dtype == "float":
            Xq = Xte * s
        else:
            Xq = np.trunc(Xte * s)  # integer truncation as in C
        pred = clf.predict(Xq)
        acc = accuracy_score(yte, pred)
        if ref_pred is None:
            ref_pred = pred
            agree = 1.0
        else:
            agree = np.mean(pred == ref_pred)
        print(f"{dtype:>10s} {s:>7.0f} {size_kb:>10.1f} {acc:>9.3f} {agree:>14.1%}")

    print(f"\nLabel order: {labels}")
    print("Deploy: copy out_dtypes/fan_model_<dtype>.h over platformio/src/fan_model.h,")
    print("multiply the C features by the scale factor above before fan_model_predict(),")
    print("rebuild, and compare flash (build summary) + latency (serial 'model ... us').")
    print("NOTE: this Python check approximates C integer behaviour; the golden-window")
    print("static tests on the device remain the ground truth (4-step ladder!).")


if __name__ == "__main__":
    main()
