# Module 7 worksheet — the model shoot-out

Team: ________________  Date: ________

Fill in one row per model you deployed. Bring this to the end-of-module discussion (and keep it — Module 9 adds quantised rows to the same table).

## Common settings

| | Value |
|---|---|
| Sample rate | ______ Hz |
| Window length | ______ samples ( ______ ms) |
| Window overlap | ______ % |
| Classes | ______________________________________ |
| Test-set size | ______ windows |

## Scoreboard

| Model | Test accuracy | Flash Δ (kB) | RAM Δ (kB) | Inference time | Notes |
|---|---|---|---|---|---|
| RF — emlearn, `float` | % | | | µs | trees: ____ depth: ____ |
| Dense NN — EI, float32 | % | | | ms | DSP block: __________ |
| 1D-CNN — EI, float32 | % | | | ms | filters/units: ______ |

- *Flash/RAM Δ* = build-summary value minus your baseline build (model call commented out). For EI models also note the `EI_CLASSIFIER` estimates from `model_metadata.h`.
- *Inference time* = median of ≥ 20 `micros()` measurements around the model call only (exclude sampling). For EI models, note DSP time and classification time separately if you enable `debug=true` in `run_classifier`.

## Questions

1. Which model gives the best **accuracy per kilobyte of flash**?

2. Which confusion (which pair of classes) is hardest for *every* model? What does that tell you about the data rather than the models?

3. The CNN sees raw data; the RF sees your handcrafted features. Where did your Module 5 domain knowledge show up in the numbers?

4. You must ship one of these in a battery-powered product tomorrow. Which one, and what is the *second* reason (after accuracy)?

5. Predict (before Module 9): what will int8 quantisation do to each row — accuracy, flash, latency?
