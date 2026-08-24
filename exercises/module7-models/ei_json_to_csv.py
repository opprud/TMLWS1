#!/usr/bin/env python3
"""
ei_json_to_csv.py - Convert an Edge Impulse data export into the per-recording
CSV layout used by Module 7 (rf-features/train_rf.py), Module 8 (anomaly
notebooks) and Module 9 (emlearn_dtype_compare.py, pruning notebook).

Input : an Edge Impulse export, either
          * a directory of .json sample files (flat, or containing the
            training/ + testing/ subfolders that EI's export zip uses), or
          * the export .zip itself (it is unpacked in memory).
        Each file is one sample in the EI ingestion JSON format:
          payload.values      = [[x, y, z], ...]   (one row per sample)
          payload.sensors     = [{"name": "accX", ...}, ...]
          payload.interval_ms = sample period in ms
        The label is the filename prefix up to the first dot - EI exports
        samples as <label>.<original-name>.json.

Output: <outdir>/<label>.<nnnnn>.csv with header timestamp,x,y,z
        (timestamp in ms; exactly what train_rf.py's loader expects).

Stdlib only (json/csv/argparse) - nothing to pip-install mid-course.

Usage (from exercises/module7-models/):
    python ei_json_to_csv.py path/to/ei-export           # dir with .json files
    python ei_json_to_csv.py fan-project-export.zip      # the export zip as-is
    python ei_json_to_csv.py export/ -o rf-features/data/raw

Troubleshooting: if every file is reported "not valid JSON", you exported
CBOR - re-export from Studio as JSON.
"""

import argparse
import csv
import io
import json
import os
import sys
import zipfile

DEFAULT_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "rf-features", "data", "raw")


def iter_json_docs(src):
    """Yield (filename, parsed_json) for every .json sample under src.

    src may be a directory (searched recursively, so EI's training/ +
    testing/ layout works unchanged) or an EI export .zip.
    """
    if os.path.isfile(src) and src.lower().endswith(".zip"):
        with zipfile.ZipFile(src) as zf:
            for name in sorted(zf.namelist()):
                base = os.path.basename(name)
                if not base.endswith(".json") or base.startswith("."):
                    continue
                with zf.open(name) as f:
                    yield base, _parse(base, io.TextIOWrapper(f, encoding="utf-8"))
    elif os.path.isdir(src):
        for root, _dirs, files in os.walk(src):
            for base in sorted(files):
                if not base.endswith(".json") or base.startswith("."):
                    continue
                with open(os.path.join(root, base), encoding="utf-8") as f:
                    yield base, _parse(base, f)
    else:
        raise SystemExit(f"{src}: not a directory or .zip file")


def _parse(name, fileobj):
    try:
        return json.load(fileobj)
    except (json.JSONDecodeError, UnicodeDecodeError):
        print(f"  WARNING: {name} is not valid JSON (CBOR export? re-export "
              "as JSON from Studio) - skipped", file=sys.stderr)
        return None


def axis_columns(sensors):
    """Map payload.sensors names (accX/accY/accZ, x/y/z, ...) to column
    indices. Falls back to file order if the names don't end in x/y/z."""
    idx = {}
    for i, s in enumerate(sensors or []):
        c = str(s.get("name", "")).strip().lower()[-1:]
        if c in "xyz" and c not in idx:
            idx[c] = i
    if all(c in idx for c in "xyz"):
        return idx["x"], idx["y"], idx["z"]
    return 0, 1, 2


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1],
                                 epilog="See the module docstring for details.")
    ap.add_argument("src", help="EI export: directory of .json files, or the export .zip")
    ap.add_argument("-o", "--out", default=DEFAULT_OUT,
                    help=f"output directory (default: {DEFAULT_OUT})")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    counters = {}   # label -> next index
    written = 0

    for name, doc in iter_json_docs(args.src):
        if doc is None:
            continue
        payload = doc.get("payload", {})
        values = payload.get("values")
        if not values:
            print(f"  WARNING: {name} has no payload.values - skipped",
                  file=sys.stderr)
            continue

        label = name.split(".")[0]
        interval_ms = float(payload.get("interval_ms", 4))    # 4 ms = 250 Hz
        ix, iy, iz = axis_columns(payload.get("sensors"))

        index = counters.get(label, 0)
        counters[label] = index + 1
        out_path = os.path.join(args.out, f"{label}.{index:05d}.csv")

        with open(out_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["timestamp", "x", "y", "z"])
            for i, row in enumerate(values):
                w.writerow([f"{i * interval_ms:g}",
                            row[ix], row[iy], row[iz]])
        written += 1

    if written == 0:
        raise SystemExit("No samples converted - check the export path/format.")
    print(f"Wrote {written} CSV files to {args.out}:")
    for label in sorted(counters):
        print(f"  {label}: {counters[label]} recordings")


if __name__ == "__main__":
    main()
