# Module 8 — Anomaly Detection on the Fan

Your Module 7 classifier only knows the states you taught it — and a softmax always answers. In this lab you build detectors for the states you *didn't* teach it.

Two tracks; do both if time allows (the notebook track builds the intuition the device track relies on):

| Track | What | Where |
|---|---|---|
| 1 | K-means → GMM → autoencoder on your fan features | [`notebooks/`](notebooks/) |
| 2 | EI K-means anomaly block, trained on normal-only, deployed to the RAK4631 | this README, below |

## The experimental trick: hold out a fault

Pick **one fault state and pretend it doesn't exist** during training — ideally the worn fan (bearing wear), or `scrape` if you have no worn fan. That class becomes your stand-in for "the fault nobody recorded". A good anomaly detector must flag it **without ever having seen it**.

## Track 1 — Notebooks

Work through in order (each ends with a hand-off to the next):

1. `01_kmeans_anomaly.ipynb` — distance-to-centroid scoring; synthetic warm-up, then your fan features; ends where K-means breaks (elliptic clusters)
2. `02_gmm_anomaly.ipynb` — likelihood scoring with Gaussian mixtures; fixes the elliptic case; compares against K-means on the same fan features
3. `03_autoencoder_anomaly.ipynb` — reconstruction error on raw windows; synthetic vibration data, then your fan windows

Prerequisite: fan CSVs in `../module7-models/rf-features/data/raw/` (the notebooks reuse the Module 7 loader and feature code). If that folder is still empty, convert your Edge Impulse export first:

```bash
python ../module7-models/ei_json_to_csv.py path/to/ei-export/   # dir of .json files, or the export .zip
```

(Same step as Module 7 Step 1 — if you did that lab, the CSVs are already there.)

## Track 2 — Edge Impulse anomaly block on device

Extends your Module 7 `ei-deploy` project. Based on the course's proven EI anomaly workflow (data forwarder → impulse → K-means block → live testing → C++ deploy).

### B1 — Add the block

1. Open your fan project in Studio → **Create impulse** → *Add a learning block* → **Anomaly Detection (K-means)**. It sits **next to** your classifier and shares the Spectral Analysis features.
2. On the **Anomaly detection** tab:
   - *Select suggested axes* — or pick the spectral axes with the highest feature importance (RMS + low-band power carried the fan classes in Module 5).
   - Cluster count: 32 (default) is fine to start.
3. **Important — normal-only training:** make sure the anomaly block trains only on `normal` (and optionally `off`) data. Remove/disable your held-out fault class from the training set entirely (Data acquisition → filter → disable, or move to test). <!-- VERIFY: current Studio UI for excluding classes from the anomaly block -->
4. Train the block. The cluster plot should hug the normal data.

### B2 — Verify in Studio before deploying

1. **Live classification**: stream a `normal` window → classifier confident, **anomaly score ≈ 0 or negative**.
2. Stream your held-out fault → anomaly score **clearly higher** (typically > 0.3–1+; scale depends on your features). Note the two score levels — your device threshold sits between them.
3. If the scores don't separate: revisit axis selection (fewer, more discriminative axes) before touching anything else.

### B3 — Redeploy and gate the classifier

1. **Deployment** → Arduino library → build → replace the folder in your PlatformIO `lib/` (delete the old one first — stale `tflite-model/` files love to linger).
2. The export now defines `EI_CLASSIFIER_HAS_ANOMALY 1` and fills `result.anomaly`. Add the gate to `main.cpp`:

```cpp
#define ANOMALY_THRESHOLD 0.5f   // start midway between your Studio 'known'/'unknown' scores

run_classifier(&signal, &result, false);

#if EI_CLASSIFIER_HAS_ANOMALY
Serial.printf("anomaly score: %.3f\n", result.anomaly);
if (result.anomaly > ANOMALY_THRESHOLD) {
    Serial.println("=> ANOMALY - unknown machine state (classifier suppressed)");
    digitalWrite(LED_BLUE, HIGH);
} else
#endif
{
    print_best_class(&result);   // your Module 7 reporting code
    digitalWrite(LED_BLUE, LOW);
}
```

3. Flash, mount on the fan and fill in your observations:

| Fan state | In training? | Top class (conf) | Anomaly score | Verdict |
|---|---|---|---|---|
| normal | yes | | | |
| imbalance | yes | | | |
| blocked | yes | | | |
| held-out fault (______) | **no** | | | should be ANOMALY |

### Expected result

Trained states classify as before with low anomaly scores; the held-out fault produces a (possibly confident!) wrong classification **and** a high anomaly score — the gate suppresses the lie and lights `LED_BLUE`. That one-two is the whole point of the module.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `result.anomaly` always 0 | The deployed library was built *before* you added the block, or the block didn't train. Rebuild the deployment; check `EI_CLASSIFIER_HAS_ANOMALY` in `model_metadata.h`. |
| Anomaly score high for *everything*, including normal | The block trained on too little normal data, or your live signal differs from training (mounting changed, fan supply voltage different). Re-record a fresh `normal` baseline in the current mounting. |
| Held-out fault scores low | Its vibration signature may genuinely resemble normal in the selected axes. Add axes with frequency-band content, or lower the cluster count (tighter normal). |
| Score jitters across the threshold | Average the score over N windows before deciding — trend, don't twitch (this is what production systems do). |
| Notebook scores don't match Studio's | Expected: different feature sets and scaling. Compare *separation*, not absolute values. |

## Checkpoint

Device demo: trained states classify normally; the held-out fault triggers the anomaly gate. Table above filled in, threshold value written down.
