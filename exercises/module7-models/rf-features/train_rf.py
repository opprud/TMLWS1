#!/usr/bin/env python3
"""
Module 7.1 - Train a Random Forest on fan vibration features and convert to C.

Input : data/raw/<label>.<index>.csv  with columns timestamp,x,y,z
        (convert an Edge Impulse JSON export with ../ei_json_to_csv.py)
Output: platformio/src/fan_model.h      (emlearn-converted model)
        platformio/src/feature_scale.h  (the int16 quantisation the model expects)
        platformio/src/test_windows.h   (one golden raw window per class + expected label)

--print-features prints the 13 feature names + float values + quantised int16
values for every golden window, for diffing against the device's output.

emlearn's tree runtime is FIXED-POINT: EmlTreesNode.value is an int16_t (see
lib/emlearn/eml_trees.h), and the generated predict() takes `const int16_t *`.
So the features are quantised to int16 BEFORE training, and the firmware applies
the identical per-feature scale — see quantise() and choose_scales() below.

The 13 features computed here MUST stay in sync with platformio/src/features.h:
  std, MAD, kurtosis, RMS per axis (x,y,z) + mean resultant magnitude.
Kurtosis uses the *biased Fisher* estimator (m4/m2^2 - 3) to keep the C
implementation trivial. (pandas .kurtosis() uses the unbiased estimator and
will NOT match the C code bit-for-bit -- we deliberately avoid it here.)
"""

import argparse
import copy
import glob
import os

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix
from sklearn.model_selection import GroupShuffleSplit

import emlearn

# --- Keep in sync with firmware (src/main.cpp) --------------------------------
SAMPLE_RATE_HZ = 250          # course-wide rate (Module 3 forwarder SAMPLE_RATE_HZ)
WINDOW = 500                  # samples per window (2 s)
HOP = 250                     # 50 % overlap -> one prediction per second
N_FEATURES = 13

DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "raw")
OUT_DIR = os.path.join(os.path.dirname(__file__), "platformio", "src")

FEATURE_NAMES = ([f"std_{a}" for a in "xyz"] + [f"mad_{a}" for a in "xyz"]
                 + [f"kurt_{a}" for a in "xyz"] + [f"rms_{a}" for a in "xyz"]
                 + ["res_mean"])

# --- int16 quantisation (see the module docstring) ----------------------------
# The 13 features live on wildly different scales: std/MAD ~0.03..2, kurtosis
# -1.5..45, RMS and the resultant ~0.1..10 (m/s^2). A single global scale would
# either crush the small features to 0 or overflow the large ones, so each
# feature gets its OWN scale factor, chosen so the largest value seen in
# TRAINING lands near Q_TARGET. int16 tops out at 32767, so that leaves ~4x
# headroom for live values above anything in the dataset; beyond that we clamp,
# which is harmless (clamping preserves ordering, so a clamped value still takes
# the same branch as the largest training value).
#
# The scales are POWERS OF TWO on purpose: they are exact in float32, so Python
# here and C on the device compute bit-identical products, and no threshold can
# drift because of a rounding difference between the two implementations.
Q_TARGET = 8192          # 2^13 — target for max|feature| after scaling
Q_MIN, Q_MAX = -32768, 32767


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


def choose_scales(X_train):
    """Per-feature power-of-two scale factor, from the TRAINING split only.

    Training-split-only is the same discipline as any other fitted preprocessing
    step (Modules 4-5): deriving the scale from the test windows too would let
    held-out data influence the deployed model, however mildly.
    """
    maxabs = np.abs(np.asarray(X_train, dtype=np.float64)).max(axis=0)
    maxabs = np.where(maxabs > 0.0, maxabs, 1.0)          # all-zero feature -> scale 1
    exponent = np.floor(np.log2(Q_TARGET / maxabs))
    exponent = np.clip(exponent, -8, 15)                  # keep the scale sane either way
    return (2.0 ** exponent).astype(np.float32)


def quantise(feats, scale):
    """Float features -> int16, EXACTLY as platformio/src/features.h does.

    float32 throughout, clamp, then round half away from zero (C's
    `(int16_t)(v + 0.5f)` for positives, `(v - 0.5f)` for negatives) — numpy's
    default round-half-to-even would disagree with the firmware on ties.
    """
    v = np.asarray(feats, dtype=np.float32) * np.asarray(scale, dtype=np.float32)
    v = np.clip(v, np.float32(Q_MIN), np.float32(Q_MAX))
    return (np.floor(np.abs(v) + np.float32(0.5)) * np.sign(v)).astype(np.int16)


def align_thresholds_for_int_features(clf):
    """Make emlearn's integer comparison mean exactly what sklearn's meant.

    sklearn sends a sample LEFT when `x <= threshold`; emlearn's runtime sends it
    left when `x < node.value`, and emlearn writes that node value with `int(t)`
    — i.e. TRUNCATED. With integer features, `x <= t` is `x < floor(t) + 1`, so a
    threshold of 1234.5 must reach the C header as 1235, not 1234. Truncation
    would misroute exactly those samples whose feature equals floor(t): rare, but
    a silent, data-dependent disagreement between the model you measured in
    Python and the one you flashed.

    Returns a COPY with thresholds rewritten; the original stays untouched so the
    accuracy printed above still refers to the model we actually deploy (the two
    are equivalent by construction — that is the point).
    """
    fixed = copy.deepcopy(clf)
    for est in fixed.estimators_:
        tree = est.tree_
        inner = tree.children_left != -1              # leaves carry a sentinel threshold
        th = tree.threshold.copy()
        th[inner] = np.floor(th[inner]) + 1.0
        tree.threshold[:] = th
    return fixed


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
    ytr, yte = y_int[tr_idx], y_int[te_idx]
    rte = X_raw[te_idx]

    print(f"Files: {n_files}   Windows: train {len(tr_idx)} / test {len(te_idx)}  "
          "(split by recording, not by window)")
    print(f"Label order (class index in C): {labels}")

    # --- Quantise to int16 ----------------------------------------------------
    # The model is trained on the integers the DEVICE will feed it, not on the
    # floats — so what we measure below is what runs on the board.
    scale = choose_scales(X[tr_idx])
    Xq = quantise(X, scale)
    Xtr, Xte = Xq[tr_idx], Xq[te_idx]
    print("Feature quantisation (train max -> int16):")
    for i, name in enumerate(FEATURE_NAMES):
        fmax = np.abs(X[tr_idx][:, i]).max()
        print(f"  {name:10s} x{scale[i]:<9g} max|f|={fmax:9.4f} -> "
              f"q in [{Xtr[:, i].min():6d}, {Xtr[:, i].max():6d}]")
    n_clamped = int(np.sum((np.abs(X * scale) > Q_MAX)))
    if n_clamped:
        print(f"  ({n_clamped} feature values clamped to +/-{Q_MAX} — expected for "
              "outliers above the training range, harmless)")

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
    # Call convert() WITHOUT dtype=: the tree runtime is int16 and emlearn's
    # dtype overrides are broken in 0.21 and 0.23 alike — dtype='float' emits
    # float literals into the int16_t node table ("narrowing conversion", the
    # firmware build fails), and dtype='int16' emits `const int16 *features`,
    # which is not a C type. Same trap as Module 6; the default path is correct.
    os.makedirs(OUT_DIR, exist_ok=True)
    deployed = align_thresholds_for_int_features(clf)
    cmodel = emlearn.convert(deployed, method="inline")
    model_path = os.path.join(OUT_DIR, "fan_model.h")
    cmodel.save(file=model_path, name="fan_model")
    print(f"Wrote {model_path}")

    # --- The scale factors the firmware must apply ----------------------------
    scale_lines = [
        "// AUTO-GENERATED by train_rf.py - do not edit.",
        "// Per-feature int16 quantisation for fan_model.h. Regenerated WITH the",
        "// model: a stale copy silently moves every split threshold.",
        "#pragma once",
        "",
        f"#define FEATURE_Q_MIN ({Q_MIN})",
        f"#define FEATURE_Q_MAX ({Q_MAX})",
        "",
        "// feature_scale[i] = the power of two feature i was multiplied by before",
        "// training. Order matches features.h / FEATURE_NAMES.",
        "static const float feature_scale[13] = {",
    ]
    for i, name in enumerate(FEATURE_NAMES):
        fmax = np.abs(X[tr_idx][:, i]).max()
        scale_lines.append(f"    {scale[i]:>9.1f}f,   // [{i:2d}] {name:10s} "
                           f"train max|f| = {fmax:8.4f}")
    scale_lines.append("};")
    scale_path = os.path.join(OUT_DIR, "feature_scale.h")
    with open(scale_path, "w") as f:
        f.write("\n".join(scale_lines) + "\n")
    print(f"Wrote {scale_path}")

    # --- Does the generated C agree with sklearn? -----------------------------
    # emlearn compiles and runs the header it just wrote, so this compares the
    # ACTUAL C model against the Python one on every window. It needs a host C
    # compiler; without one, the golden-window tests (host_test.c / on-device)
    # still cover the same ground on 5 windows.
    #
    # align_thresholds_for_int_features() above makes the ROUTING identical.
    # Aggregation is not guaranteed identical: sklearn averages the trees' class
    # probabilities, emlearn's runtime takes a majority vote of their hard
    # labels. At max_depth=8 the leaves are near-pure so the two coincide — but
    # that is a property of this forest, not a promise, which is why we check
    # every window instead of trusting the conversion.
    try:
        em_pred = np.asarray(cmodel.predict(Xq))
    except Exception as exc:
        print(f"\nSkipped C-vs-Python check (no compiler for emlearn?): {exc}")
    else:
        disagree = int(np.sum(em_pred != clf.predict(Xq)))
        print(f"\nC-vs-Python check: {len(Xq) - disagree}/{len(Xq)} windows agree")
        if disagree:
            raise SystemExit(
                f"FAIL: the generated C model disagrees with sklearn on {disagree} "
                "windows — do not flash this. Check that quantise() here and "
                "quantise_features() in features.h still match.")

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

    # Sanity: model prediction on the golden feature vectors (quantised, as on
    # the device). These are the same 5 windows host_test.c and the firmware run.
    for name, ci in tw_names:
        w = rte[np.where(yte == ci)[0][0]]
        q = quantise(extract_features(w), scale)
        p = clf.predict(q.reshape(1, -1))[0]
        flag = "OK " if p == ci else "MISMATCH"
        print(f"  golden '{labels[ci]}' -> predicted '{labels[p]}' {flag}")

    # --print-features: the reference values to diff against the device when
    # the static tests FAIL (see README troubleshooting). Both columns matter —
    # a float match with an int mismatch means the scales are out of sync.
    if args.print_features:
        print("\nGolden-window features (Python reference, float32 windows):")
        for name, ci in tw_names:
            w = rte[np.where(yte == ci)[0][0]]
            feats = extract_features(w)
            q = quantise(feats, scale)
            print(f"  window '{labels[ci]}':")
            for fname, val, qv, s in zip(FEATURE_NAMES, feats, q, scale):
                print(f"    {fname:10s} {val:12.6f}  x{s:<9g} -> {qv:6d}")


if __name__ == "__main__":
    main()
