# Module 7 — Build a Model and Deploy It

Three models on your fan dataset, all deployed to the RAK4631, all measured. The deliverable is a filled-in [comparison worksheet](comparison-worksheet.md).

| Track | Model | Path | Folder |
|---|---|---|---|
| 7.1 *(mandatory)* | Random Forest on features | scikit-learn → emlearn header | [`rf-features/`](rf-features/) |
| 7.2 | Dense NN on DSP features | Edge Impulse → Arduino library | [`ei-deploy/`](ei-deploy/) |
| 7.3 | 1D-CNN on raw windows | Edge Impulse (second impulse) | [`ei-deploy/`](ei-deploy/) (§ CNN variant) |

## Prerequisites

- Fan dataset recorded in Module 4 (Edge Impulse project + raw CSV exports)
- Module 5 feature notebook results (which features separate your classes)
- Working PlatformIO + RAK4631 toolchain (Module 2 / setup guide)
- Python env with `scikit-learn`, `emlearn` (`pip list | grep emlearn`)

## Ground rules (all tracks)

1. **Window discipline:** the window length/rate used in training **must** equal the firmware window. Default in this material: **100 Hz, 200-sample windows, 50 % overlap**. <!-- VERIFY: match whatever was fixed in Modules 4–5 -->
2. **Validate on the 4-step ladder** before trusting live data: Python → C-on-laptop → C-on-device with static arrays → live sensor.
3. **Measure everything** for the worksheet: accuracy (held-out test set), flash & RAM (PlatformIO build summary delta vs a baseline build), latency (`micros()` around inference, median of ≥ 20 runs).

## Measuring flash/RAM deltas

Build the project **once with the model call commented out** (baseline) and once for real; subtract the build-summary numbers:

```
RAM:   [====      ]  38.2% (used 100136 bytes from 262144 bytes)
Flash: [===       ]  31.0% (used 316228 bytes from 1044480 bytes)
```

## Suggested timing (3 h block)

- 0:00 – 1:00 Track 7.1 (RF end-to-end)
- 1:00 – 2:00 Track 7.2 (EI dense NN deploy)
- 2:00 – 2:40 Track 7.3 (CNN impulse) — or polish 7.1/7.2
- 2:40 – 3:00 Fill worksheet, compare with the other teams

## Checkpoint

Live fan classification printing on serial for ≥ 2 of the 3 models, plus a completed worksheet row for each deployed model.
