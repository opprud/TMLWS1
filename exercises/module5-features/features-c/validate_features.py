#!/usr/bin/env python3
"""Module 5 Track B — validate the on-device C features against numpy.

Usage:
    python validate_features.py --port /dev/cu.usbmodemXXXX          # synthetic golden window
    python validate_features.py --port COM5 --csv include/golden/win_normal.csv

The device (features-c firmware) prints a FEATURES_BEGIN ... FEATURES_END block
every 5 seconds. This script computes the SAME features on the SAME window in
numpy (float64) and compares.

Conventions (must match features.h / features.cpp — do not "fix" one side only):
  std  = population std (divide by N)
  zc   = sign changes of (x[i]-mean)*(x[i-1]-mean) < 0
  band = Hann-windowed rfft, |X|^2 summed into 5 equal bands over [0, fs/2),
         DC and Nyquist bins excluded.
"""

import argparse
import re
import sys

import numpy as np

try:
    import serial  # pyserial
except ImportError:
    sys.exit("pyserial missing: pip install pyserial")

FS = 100.0
N = 256
N_BANDS = 5

REL_TOL_STATS = 1e-4   # time-domain features
REL_TOL_BANDS = 1e-3   # float32 FFT vs float64 numpy
ABS_TOL = 1e-6         # for values near zero (e.g. mean of a zero-mean signal)


def make_synthetic_window(n=N, fs=FS):
    """Identical to make_synthetic_window() in src/main.cpp."""
    i = np.arange(n)
    t = i / fs
    return (0.8 * np.sin(2 * np.pi * 25.0 * t)
            + 0.3 * np.sin(2 * np.pi * 40.0 * t)
            + 0.05 * np.sin(2 * np.pi * 3.1 * t + 1.0))


def reference_features(x, fs=FS, n_bands=N_BANDS):
    x = np.asarray(x, dtype=float)
    mean = x.mean()
    feats = {
        "mean": mean,
        "std": x.std(),                                  # population
        "rms": np.sqrt(np.mean(x ** 2)),
        "min": x.min(),
        "max": x.max(),
        "zc": float(np.sum((x[:-1] - mean) * (x[1:] - mean) < 0)),
    }
    X = np.fft.rfft(x * np.hanning(len(x)))
    freqs = np.fft.rfftfreq(len(x), d=1 / fs)
    mag2 = np.abs(X) ** 2
    band_hz = (fs / 2) / n_bands
    for b in range(n_bands):
        sel = (freqs >= b * band_hz) & (freqs < (b + 1) * band_hz)
        sel[0] = False                                   # exclude DC
        feats[f"band{b}"] = mag2[sel].sum()
    return feats


def read_device_block(port, baud=115200, timeout_s=15):
    """Read one FEATURES_BEGIN..END block and return dict of key->float."""
    ser = serial.Serial(port, baud, timeout=1)
    lines, capturing, waited = [], False, 0
    try:
        while waited < timeout_s:
            raw = ser.readline().decode(errors="replace").strip()
            if not raw:
                waited += 1
                continue
            if raw == "FEATURES_BEGIN":
                capturing, lines = True, []
                continue
            if raw == "FEATURES_END" and capturing:
                break
            if capturing:
                lines.append(raw)
        else:
            sys.exit(f"timeout: no FEATURES block within {timeout_s}s "
                     f"(is the firmware flashed? is another monitor holding the port?)")
    finally:
        ser.close()

    out = {}
    for line in lines:
        for key, val in re.findall(r"(\w+)=(\S+)", line):
            if key in ("n", "fs", "window", "axis"):
                out[f"_{key}"] = val
            else:
                try:
                    out[key] = float(val)
                except ValueError:
                    out[f"_{key}"] = val
    return out


def compare(ref, dev):
    print(f"{'feature':<10} {'python':>16} {'device':>16} {'rel.err':>12}  result")
    print("-" * 66)
    all_ok = True
    for key, r in ref.items():
        if key not in dev:
            print(f"{key:<10} {'-':>16} {'-':>16} {'-':>12}  MISSING")
            all_ok = False
            continue
        d = dev[key]
        tol = REL_TOL_BANDS if key.startswith("band") else REL_TOL_STATS
        denom = max(abs(r), ABS_TOL)
        rel = abs(r - d) / denom
        ok = rel < tol
        all_ok &= ok
        print(f"{key:<10} {r:>16.6g} {d:>16.6g} {rel:>12.2e}  {'PASS' if ok else 'FAIL'}")
    return all_ok


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", required=True, help="serial port (/dev/cu.usbmodem*, /dev/ttyACM0, COMx)")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--csv", help="validate against this exported window instead of the "
                                  "synthetic one (device must run the matching golden header)")
    args = ap.parse_args()

    x = np.loadtxt(args.csv) if args.csv else make_synthetic_window()
    if len(x) != N:
        sys.exit(f"window has {len(x)} samples, expected {N}")

    ref = reference_features(x)
    print(f"waiting for device on {args.port} ...")
    dev = read_device_block(args.port, args.baud)
    print(f"device window: {dev.get('_window', '?')}  n={dev.get('_n', '?')}  "
          f"fs={dev.get('_fs', '?')}")
    if args.csv and dev.get("_window") == "synthetic":
        print("WARNING: device is running the synthetic window but you passed --csv.\n"
              "         Enable the golden header in src/main.cpp and re-flash.")

    ok = compare(ref, dev)
    if "stats_us" in dev or "fft_us" in dev:
        print(f"\ntiming: stats={dev.get('stats_us', float('nan')):.0f} us, "
              f"fft={dev.get('fft_us', float('nan')):.0f} us")
    print("\nALL PASS ✔" if ok else "\nFAILURES — check the conventions list in the header of this script.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
