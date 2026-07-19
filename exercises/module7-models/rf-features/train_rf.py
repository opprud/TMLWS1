#!/usr/bin/env python3
"""
Module 7.1 - Train a Random Forest on fan vibration features and convert to C.

Input : data/raw/<label>.<index>.csv  with columns timestamp,x,y,z
        (convert an Edge Impulse JSON export with ../ei_json_to_csv.py)
Output: platformio/src/fan_model.h     (emlearn-converted model)
        platformio/src/test_windows.h  (one golden raw window per class + expected label)

--print-features prints the 13 feature names + values for every golden
window, for diffing against the device's feature output.

The 13 features computed here MUST stay in sync with platformio/src/features.h:
  std, MAD, kurtosis, RMS per axis (x,y,z) + mean resultant magnitude.
Kurtosis uses the *biased Fisher* estimator (m4/m2^2 - 3) to keep the C
implementation trivial. (pandas .kurtosis() uses the unbiased estimator and
will NOT match the C code bit-for-bit -- we deliberately avoid it here.)
"""

import argparse
import glob
import os

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix
from sklearn.model_selection import GroupShuffleSplit

import emlearn

# --- Keep in sync with firmware (src/main.cpp) --------------------------------
SAMPLE_RATE_HZ = 100          # VERIFY: match the rate used in Modules 4-5
WINDOW = 200                  # samples per window (2 s)
HOP = 100                     # 50 % overlap
N_FEATURES = 13

DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "raw")
OUT_DIR = os.path.join(os.path.dirname(__file__), "platformio", "src")

FEATURE_NAMES = ([f"std_{a}" for a in "xyz"] + [f"mad_{a}" for a in "xyz"]
                 + [f"kurt_{a}" for a in "xyz"] + [f"rms_{a}" for a in "xyz"]
                 + ["res_mean"])


def kurtosis_biased(x):
    """Fisher (excess) kurtosis, biased estimator: m4/m2^2 - 3. Matches features.h."""
    x = np.asarray(x, dtype=np.float64)
    m = x.mean()
    m2 = np.mean((x - m) ** 2)
    m4 = np.mean((x - m) ** 4)
    if m2 == 0:
        return 0.0
    return m4 / (m2 * m2) - 3.0


def extract_features(win):
    """win: (WINDOW, 3) array of x,y,z acceleration. Returns 13 features."""
    feats = []
    for ax in range(3):
        v = win[:, ax]
        feats.append(np.std(v))                                  # std
    for ax in range(3):
        v = win[:, ax]
        feats.append(np.mean(np.abs(v - np.mean(v))))            # MAD
    for ax in range(3):
        feats.append(kurtosis_biased(win[:, ax]))                # kurtosis
    for ax in range(3):
        v = win[:, ax]
        feats.append(np.sqrt(np.mean(v * v)))                    # RMS
    resultant = np.sqrt(np.sum(win**2, axis=1))
    feats.append(np.mean(resultant))                             # mean resultant
    return np.array(feats, dtype=np.float32)


def load_windows(data_dir):
    X_raw, X_feat, y, groups = [], [], [], []
    files = sorted(glob.glob(os.path.join(data_dir, "*.csv")))
    if not files:
        raise SystemExit(f"No CSV files found in {data_dir} - see README step 1 "
                         "(../ei_json_to_csv.py converts an EI export).")
    for fi, path in enumerate(files):
        label = os.path.basename(path).split(".")[0]
        data = np.genfromtxt(path, delimiter=",", skip_header=1)
        if data.ndim != 2 or data.shape[1] < 4:
            print(f"  skipping {path} (unexpected shape {data.shape})")
            continue
        xyz = data[:, 1:4]
        for start in range(0, len(xyz) - WINDOW + 1, HOP):
            win = xyz[start:start + WINDOW]
            X_raw.append(win.astype(np.float32))
            X_feat.append(extract_features(win))
            y.append(label)
            groups.append(fi)   # source recording, for the group-level split
    return (np.array(X_raw), np.array(X_feat), np.array(y),
            np.array(groups), len(files))


def c_float_array(name, arr, per_line=8):
    flat = np.asarray(arr, dtype=np.float32).flatten()
    lines = [f"static const float {name}[] = {{"]
    for i in range(0, len(flat), per_line):
        chunk = ", ".join(f"{v:.6f}f" for v in flat[i:i + per_line])
        lines.append(f"    {chunk},")
    lines.append("};")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--print-features", action="store_true",
                    help="print the 13 feature names + values per golden window "
                         "(diff against the device output when static tests FAIL)")
    args = ap.parse_args()

    X_raw, X, y, groups, n_files = load_windows(DATA_DIR)
    labels = sorted(np.unique(y))                    # alphabetical = class index order
    y_int = np.array([labels.index(v) for v in y])

    # Split by *source recording*, not by window: 50 %-overlapping windows from
    # the same recording are near-duplicates, and a window-level split would
    # leak them across train/test and inflate the accuracy (the leakage rule
    # from Modules 4-5). This also keeps the printed accuracy comparable with
    # EI's recording-level held-out test set on the worksheet.
    # Needs >= 2 recordings per class so every class can land in the test set.
    gss = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=42)
    tr_idx, te_idx = next(gss.split(X, y_int, groups=groups))
    Xtr, Xte = X[tr_idx], X[te_idx]
    ytr, yte = y_int[tr_idx], y_int[te_idx]
    rte = X_raw[te_idx]

    print(f"Files: {n_files}   Windows: train {len(Xtr)} / test {len(Xte)}  "
          "(split by recording, not by window)")
    print(f"Label order (class index in C): {labels}")

    clf = RandomForestClassifier(n_estimators=10, max_depth=8, random_state=42)
    clf.fit(Xtr, ytr)
    pred = clf.predict(Xte)
    print(f"Test accuracy: {accuracy_score(yte, pred):.3f}")
    print("Confusion matrix (rows=true, cols=pred):")
    print(confusion_matrix(yte, pred))
    print("Feature importances:")
    for n, imp in sorted(zip(FEATURE_NAMES, clf.feature_importances_),
                         key=lambda t: -t[1]):
        print(f"  {n:10s} {imp:.3f}")

    # --- Convert to C ---------------------------------------------------------
    os.makedirs(OUT_DIR, exist_ok=True)
    cmodel = emlearn.convert(clf, method="inline")   # dtype='float'; ints in Module 9
    model_path = os.path.join(OUT_DIR, "fan_model.h")
    cmodel.save(file=model_path, name="fan_model")
    print(f"Wrote {model_path}")

    # --- Golden test vectors: one test-set window per class -------------------
    lines = [
        "// AUTO-GENERATED by train_rf.py - do not edit.",
        "// One golden raw window per class, taken from the *test* set.",
        "#pragma once",
        f"#define TEST_WINDOW_LEN {WINDOW}",
        f"#define TEST_N_CLASSES {len(labels)}",
        "static const char *const class_names[TEST_N_CLASSES] = {"
        + ", ".join(f'"{l}"' for l in labels) + "};",
    ]
    tw_names = []
    for ci, label in enumerate(labels):
        idx = np.where(yte == ci)[0]
        if len(idx) == 0:
            print(f"  WARNING: no test window for class '{label}', skipping golden vector")
            continue
        win = rte[idx[0]]                            # (WINDOW, 3)
        name = f"test_window_{label}"
        tw_names.append((name, ci))
        lines.append(c_float_array(name, win))       # interleaved x,y,z per row
    lines.append(f"#define TEST_N_WINDOWS {len(tw_names)}")
    lines.append("static const float *const test_windows[TEST_N_WINDOWS] = {"
                 + ", ".join(n for n, _ in tw_names) + "};")
    lines.append("static const int test_expected[TEST_N_WINDOWS] = {"
                 + ", ".join(str(c) for _, c in tw_names) + "};")
    tw_path = os.path.join(OUT_DIR, "test_windows.h")
    with open(tw_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Wrote {tw_path}")

    # Sanity: model prediction on the golden feature vectors
    for name, ci in tw_names:
        w = rte[np.where(yte == ci)[0][0]]
        p = clf.predict(extract_features(w).reshape(1, -1))[0]
        flag = "OK " if p == ci else "MISMATCH"
        print(f"  golden '{labels[ci]}' -> predicted '{labels[p]}' {flag}")

    # --print-features: the reference values to diff against the device when
    # the static tests FAIL (see README troubleshooting).
    if args.print_features:
        print("\nGolden-window features (Python reference, float32 windows):")
        for name, ci in tw_names:
            w = rte[np.where(yte == ci)[0][0]]
            feats = extract_features(w)
            print(f"  window '{labels[ci]}':")
            for fname, val in zip(FEATURE_NAMES, feats):
                print(f"    {fname:10s} {val:.6f}")


if __name__ == "__main__":
    main()
