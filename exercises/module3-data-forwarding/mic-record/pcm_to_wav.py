#!/usr/bin/env python3
"""
pcm_to_wav.py — convert a mic-record serial dump to a WAV file.

The mic-record firmware prints a recording as base64 between markers:

    -----BEGIN AUDIO base64 rate=16000 bits=16 samples=32000-----
    UklGRiQAAABXQVZFZm10IBAAAAABAAEA...
    -----END AUDIO-----

Capture the serial monitor output to a file (e.g. copy-paste from the
PlatformIO monitor, or `pio device monitor | tee capture.txt`), then:

    python3 pcm_to_wav.py capture.txt fan_normal.01.wav
    python3 pcm_to_wav.py capture.txt out.wav --rate 16125   # fallback clock
    python3 pcm_to_wav.py capture.txt --play                 # quick listen (macOS)

The sample rate is read from the BEGIN marker when present; --rate overrides.
Then upload to Edge Impulse (filename before the first '.' becomes the label):

    edge-impulse-uploader --label fan_normal --category training fan_normal.01.wav
"""

import argparse
import base64
import re
import subprocess
import sys
import wave

BEGIN_RE = re.compile(r"-----BEGIN AUDIO base64((?:\s+\w+=\d+)*)-----")
END_MARK = "-----END AUDIO-----"
B64_LINE_RE = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")


def extract_dump(text: str):
    """Return (pcm_bytes, rate_from_marker or None) for the LAST dump in text."""
    dumps = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        m = BEGIN_RE.search(lines[i])
        if not m:
            i += 1
            continue
        params = dict(
            kv.split("=") for kv in m.group(1).split() if "=" in kv
        )
        rate = int(params["rate"]) if "rate" in params else None
        b64_chunks = []
        i += 1
        while i < len(lines) and END_MARK not in lines[i]:
            line = lines[i].strip()
            if line and B64_LINE_RE.match(line):
                b64_chunks.append(line)
            i += 1
        dumps.append((base64.b64decode("".join(b64_chunks)), rate))
        i += 1

    if not dumps:
        sys.exit(
            "No '-----BEGIN AUDIO' block found in the input.\n"
            "Did you capture the full serial output, including the markers?"
        )
    if len(dumps) > 1:
        print(f"Note: found {len(dumps)} dumps — using the last one.")
    return dumps[-1]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="serial capture text file")
    ap.add_argument("output", nargs="?", default="out.wav", help="output WAV path")
    ap.add_argument("--rate", type=int, default=None,
                    help="sample rate override in Hz (default: from marker, else 16000)")
    ap.add_argument("--play", action="store_true",
                    help="play the result (afplay on macOS / aplay on Linux)")
    args = ap.parse_args()

    with open(args.input, "r", errors="replace") as f:
        pcm, marker_rate = extract_dump(f.read())

    rate = args.rate or marker_rate or 16000
    n_samples = len(pcm) // 2
    if len(pcm) % 2:
        print("Warning: odd byte count — dump may be truncated; dropping last byte.")
        pcm = pcm[:-1]

    with wave.open(args.output, "wb") as w:
        w.setnchannels(1)       # mono
        w.setsampwidth(2)       # 16-bit
        w.setframerate(rate)
        w.writeframes(pcm)      # int16 little-endian, as dumped by the Cortex-M4

    print(f"Wrote {args.output}: {n_samples} samples @ {rate} Hz "
          f"= {n_samples / rate:.2f} s, {len(pcm)} bytes")

    if args.play:
        player = "afplay" if sys.platform == "darwin" else "aplay"
        subprocess.run([player, args.output], check=False)


if __name__ == "__main__":
    main()
