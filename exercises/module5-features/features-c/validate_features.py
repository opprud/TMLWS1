#!/usr/bin/env python3
"""Module 5 Track B — validate the on-device C features against numpy.

Usage:
    python validate_features.py --port /dev/cu.usbmodemXXXX          # synthetic golden window
    python validate_features.py --port COM5 --csv include/golden/win_normal.csv

macOS: use the /dev/cu.* node, not /dev/tty.* — pyserial blocks on the tty node
waiting for carrier detect.

The device (features-c firmware) prints a FEATURES_BEGIN ... FEATURES_END block
every 5 seconds. This script computes the SAME features on the SAME window in
numpy (float64) and compares.

fs and N are taken from the device's own `n=... fs=...` report so the two sides
cannot silently drift apart (override with --fs / --n). This matters: the band
edges are (fs/2)/n_bands, so validating a 250 Hz device against a 100 Hz
reference compares 25 Hz bands with 10 Hz bands and every band* row fails while
the time-domain rows still pass.

Conventions (must match features.h / features.cpp — do not "fix" one side only):
  std  = population std (divide by N)
  zc   = sign changes of (x[i]-mean)*(x[i-1]-mean) < 0
  band = Hann-windowed rfft, |X|^2 summed into 5 equal bands over [0, fs/2),
         DC and Nyquist bins excluded.
"""

import argparse
import os
import re
import sys

import numpy as np

try:
    import serial  # pyserial
except ImportError:
    sys.exit("pyserial missing: pip install pyserial")

# Course convention (Module 4 fan recordings): 250 Hz, 512-sample windows.
# Used only when the device does not report its own n/fs.
FS_DEFAULT = 250.0
N_DEFAULT = 512        # must equal FEAT_FFT_N in include/features.h
N_BANDS = 5

REL_TOL_STATS = 1e-4   # time-domain features
REL_TOL_BANDS = 1e-3   # float32 FFT vs float64 numpy
ABS_TOL = 1e-6         # for values near zero (e.g. mean of a zero-mean signal)


def make_synthetic_window(n=N_DEFAULT, fs=FS_DEFAULT):
    """Identical to make_synthetic_window() in src/main.cpp."""
    i = np.arange(n)
    t = i / fs
    return (0.8 * np.sin(2 * np.pi * 25.0 * t)
            + 0.3 * np.sin(2 * np.pi * 40.0 * t)
            + 0.05 * np.sin(2 * np.pi * 3.1 * t + 1.0))


def reference_features(x, fs=FS_DEFAULT, n_bands=N_BANDS):
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
    ap.add_argument("--fs", type=float, help=f"sample rate in Hz; default: whatever the "
                                             f"device reports (else {FS_DEFAULT:g})")
    ap.add_argument("--n", type=int, help=f"window length in samples; default: whatever the "
                                          f"device reports (else {N_DEFAULT})")
    args = ap.parse_args()

    print(f"waiting for device on {args.port} ...")
    dev = read_device_block(args.port, args.baud)
    print(f"device window: {dev.get('_window', '?')}  n={dev.get('_n', '?')}  "
          f"fs={dev.get('_fs', '?')}")

    # Take fs/N from the device unless overridden, then refuse to continue if the
    # two sides disagree: the band edges are (fs/2)/n_bands, so a silent fs
    # mismatch fails every band* row while the time-domain rows still pass.
    dev_fs = float(dev["_fs"]) if "_fs" in dev else None
    dev_n = int(float(dev["_n"])) if "_n" in dev else None
    fs = args.fs if args.fs is not None else (dev_fs if dev_fs is not None else FS_DEFAULT)
    n = args.n if args.n is not None else (dev_n if dev_n is not None else N_DEFAULT)
    if dev_fs is not None and abs(dev_fs - fs) > 1e-6:
        sys.exit(f"fs mismatch: device says {dev_fs:g} Hz, this run uses {fs:g} Hz.\n"
                 f"         Band edges are (fs/2)/{N_BANDS}, so the band* comparison would "
                 f"be meaningless.\n"
                 f"         Fix FS in src/main.cpp and re-flash, or drop --fs.")
    if dev_n is not None and dev_n != n:
        sys.exit(f"window-length mismatch: device says n={dev_n}, this run uses n={n}.\n"
                 f"         Fix FEAT_FFT_N in include/features.h (and re-export the golden "
                 f"window from notebook 02) or drop --n.")
    print(f"comparing at fs={fs:g} Hz, n={n} ({n / fs:.3f} s window)")

    x = np.loadtxt(args.csv) if args.csv else make_synthetic_window(n, fs)
    if len(x) != n:
        sys.exit(f"window has {len(x)} samples, expected {n} — re-export the golden window "
                 f"from notebook 02 with FFT_N={n}")
    if args.csv and dev.get("_window") == "synthetic":
        print("WARNING: device is running the synthetic window but you passed --csv.\n"
              "         Enable the golden header in src/main.cpp and re-flash.")

    # Are we comparing the .csv twin of the .h that is actually flashed? The
    # firmware prints GOLDEN_NAME; without it there is nothing tying the two
    # files together and a wrong pair just looks like a broken FFT.
    dev_golden = dev.get("_golden")
    if args.csv:
        csv_name = os.path.splitext(os.path.basename(args.csv))[0]
        if dev_golden and dev_golden != csv_name:
            sys.exit(f"golden-window mismatch: the device is running '{dev_golden}', "
                     f"you passed '{csv_name}.csv'.\n"
                     f"         Point --csv at include/golden/{dev_golden}.csv, or "
                     f"re-flash with the {csv_name} header.")
        if not dev_golden:
            print("NOTE: this firmware does not report GOLDEN_NAME, so the pairing of "
                  "flashed .h\n      and --csv cannot be checked — see README B3.")
        elif dev_golden:
            print(f"golden window: {dev_golden} (device) == {csv_name}.csv (host)")

    ref = reference_features(x, fs)
    ok = compare(ref, dev)
    if "stats_us" in dev or "fft_us" in dev:
        print(f"\ntiming: stats={dev.get('stats_us', float('nan')):.0f} us, "
              f"fft={dev.get('fft_us', float('nan')):.0f} us")
    print("\nALL PASS ✔" if ok else "\nFAILURES — check the conventions list in the header of this script.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
