---
marp: true
theme: tinyml-clean
paginate: true
---

<!--
Module 8. Participants have live classifiers on the fan from Module 7 and an
EI project with a trained impulse. Narrative: classifiers are closed-world;
condition monitoring is open-world. Three unsupervised tools, then the EI
anomaly block as the deployable version.
Timing: ~50 min slides, then a two-track lab (notebooks + EI-on-device).
-->

<!-- _class: title -->

# Module 8
# Anomaly Detection

**Detecting the faults you never recorded**
TinyML Course · Day 3

---

<!--
The core problem, stated with the exact phrasing from the old EI exercise:
ML models ALWAYS predict SOMETHING. Softmax output sums to 1.0 no matter what
you feed it. Let this sink in — it's the single most important slide today.
-->

## Classifiers always answer — even when they shouldn't

- A softmax classifier with 5 classes **always** outputs 5 probabilities summing to **1.0**
- Feed it something it has never seen → it still picks a class, often confidently

```
input: bearing wear (never recorded)
output: normal 0.09 | imbalance 0.71 | blocked 0.12 | scrape 0.05 | off 0.03
                        ↑ confident. wrong.
```

> ML models *always* predict *something*, no matter what data you throw at them.
> — old course exercise, still the truth

---

<!--
Make it concrete with the fan. We trained 5 states. The real world has more
failure modes than any training set: bearing wear, resonance from mounting,
dust build-up, voltage sag. In a pump plant, the unknown fault is the expensive
one.
-->

## The open-world problem in condition monitoring

Trained states: `normal · imbalance · blocked · scrape · off`

Reality also contains:

- bearing wear (your "worn fan" — we kept it out of training on purpose)
- loose mounting / resonance
- dust build-up, voltage sag, cable rubbing the blades…

**You cannot record every fault in advance.** But you can record *normal* for as long as you like — and flag everything that stops looking like it.

---

<!--
Definition slide. Anomaly detection = model the NORMAL data density, score new
samples by how far outside it they fall. Unsupervised: no fault labels needed
for training. This inverts the data problem: normal data is cheap and abundant.
-->

## Anomaly detection — flip the problem

- **Supervised classifier:** "which of the *known* states is this?"
- **Anomaly detector:** "how far is this from *everything I saw during training*?"

Recipe (all methods today):

1. Train on **normal data only** (cheap, abundant)
2. Compute an **anomaly score** for each new window
3. Pick a **threshold** — above = anomaly

Three ways to build the score: **distance**, **likelihood**, **reconstruction error**.

---

<!--
Method 1: K-means. From the Anomaly Kmeans notebook. Fit K clusters to normal
feature vectors; score = distance to nearest centroid. Cheap: K centroids, one
Euclidean distance each. This is EXACTLY what the EI anomaly block does.
-->

## Method 1 — K-means distance scoring

1. Fit **K cluster centroids** to normal feature vectors (scikit-learn `KMeans`)
2. Score of a new window = **distance to its nearest centroid**
3. Far from every centroid → anomaly

```python
kmeans = KMeans(n_clusters=3).fit(X_normal)
d = np.min(np.linalg.norm(X_new - kmeans.cluster_centers_, axis=1))
```

- On-device cost: K × n_features multiply-adds — **microseconds**
- This is exactly Edge Impulse's *K-means Anomaly Detection* block

---

<!--
Thresholding — the engineering decision. Histogram of training-set distances,
take e.g. the 98th percentile, then sanity-tune manually. Threshold trades
false alarms vs missed faults; in condition monitoring a false alarm costs a
technician visit, a miss costs a pump.
-->

## Picking the threshold

```python
distances = [dist_to_nearest_centroid(x) for x in X_normal]
threshold = np.percentile(distances, 98)     # start at the 98th percentile
```

- Plot the histogram of *normal* scores — threshold sits at its right tail
- Then tune against reality:
  - threshold ↓ → more sensitivity, more **false alarms**
  - threshold ↑ → fewer alarms, more **missed faults**
- There is no correct value — only a cost trade-off you must own

---

<!--
K-means failure mode, straight from the notebook's punchline: elliptic /
correlated clusters. Euclidean distance draws spherical boundaries; elongated
normal-data clouds get cut off. "Now what...?" → GMM.
-->

## Where K-means breaks

- Distance-to-centroid draws **spherical** boundaries
- Real feature clouds are often **elongated and correlated** (e.g. RMS_x grows with RMS_y)
- A point can be *inside* the true normal cloud but *far* from a centroid — false alarm
- And vice versa: an anomaly can hide *between* two centroids

Notebook demo: K-means on elliptic blobs draws visibly wrong borders.

**"K-means is not really good at this — now what…?"** → give the clusters a shape.

---

<!--
Method 2: GMM, from the Anomaly GMM notebook (Géron ch.9). Each cluster is a
Gaussian with a full covariance matrix — ellipses. Score = log-likelihood via
score_samples. Threshold at a density percentile (e.g. 2%).
-->

## Method 2 — Gaussian Mixture Models

- Model normal data as a **mixture of K Gaussians** — each with mean *and covariance* → ellipses, not spheres
- Score = **log-likelihood**: `gm.score_samples(X_new)`
- *Low* likelihood = low-density region = anomaly

```python
gm = GaussianMixture(n_components=3, n_init=10).fit(X_normal)
threshold = np.percentile(gm.score_samples(X_normal), 2)
is_anomaly = gm.score_samples(X_new) < threshold
```

`covariance_type`: `spherical` (≈ K-means) → `diag` → `tied` → `full` — flexibility vs parameters.

---

<!--
GMM on device: still cheap. Evaluating K Gaussians = a few matrix-vector ops.
emlearn ships eml_mixture for exactly this → a fully open-source on-device
anomaly path exists next to EI's. EI also offers a GMM anomaly block (enterprise
feature historically — VERIFY availability on the free tier).
-->

## GMM fits on the MCU too

- Inference = evaluate K Gaussians: a handful of matrix–vector products
- **emlearn supports GMM** (`eml_mixture`) — train in scikit-learn, convert to C, same workflow as the Random Forest
- Edge Impulse also has a **GMM anomaly block** next to the K-means one
  <!-- VERIFY: EI GMM anomaly block availability on the free/community tier -->

Rule of thumb: start with K-means; reach for GMM when normal data is clearly multi-modal or correlated.

---

<!--
Method 3: autoencoder, from Autoencoder.ipynb. The constraint forces the
network to learn the structure of normal data; anomalies reconstruct badly.
Be precise about the notebook's Conv1D architecture: the latent feature map is
25×64 = 1600 values — MORE than the 200-sample input — so calling it a "narrow
bottleneck" would refute itself. The real squeeze is along the time axis
(200 → 25 steps): the decoder must rebuild fine temporal detail from a coarse
summary, which it can only do for signal shapes it has learned. The classic
dense AE (200 → 16 → 200) is the genuinely narrow variant if anyone wants the
textbook picture. Works on raw windows — no feature engineering — which is its
superpower and its cost.
-->

## Method 3 — Autoencoder reconstruction error

- Train a network to **reproduce its own input** through a constrained middle layer
- It can only do that well for data that looks like the training data
- Score = **reconstruction error** `MSE(x, x̂)`

```
raw window (200×1) → Conv1D encoder → latent 25×64 feature map → Conv1D decoder → x̂
                     score = mean((x - x̂)²)
```

- The squeeze here is **temporal**: 200 time steps → 25 (a dense AE would instead use a genuinely narrow layer, e.g. 200 → 16 → 200)
- Trained **only on normal windows** — faults were never compressible

---

<!--
The reconstruction-error picture from the notebook: normal windows cluster at
low MSE, anomalous windows (shifted frequency + spikes) at clearly higher MSE.
Two histograms barely overlap → easy threshold. Show original-vs-reconstruction
overlay: the AE "redraws" the anomaly as the nearest normal-looking signal.
-->

## What the autoencoder sees

- Normal test windows: MSE ≈ 0.002 — reconstruction hugs the signal
- Anomalous windows (shifted frequency, spikes): MSE 10–100× higher
- The decoder redraws every input as *the nearest normal-looking signal* — the residual is the fault signature

Threshold recipe is identical: percentile of **normal** reconstruction errors.

*(Notebook: synthetic 50 Hz "vibration" vs 80 Hz + spikes — you will swap in fan windows.)*

---

<!--
Honest comparison table. Note AE deployment cost: the notebook's Conv1D AE is
65k params ≈ 254 KB float32 of weights — that's flash (a quarter of the 1 MB,
next to the BSP, SoftDevice and EI SDK), and the Conv1D activations then bill
tens of kB of the 256 KB RAM on top. Deployable only after serious shrinking —
a much smaller AE and/or int8. That's why the deployable track uses K-means.
-->

## Three tools, one job

| | K-means | GMM | Autoencoder |
|---|---|---|---|
| Score | distance | likelihood | reconstruction error |
| Input | features | features | raw windows (or features) |
| Captures | blobs | elongated/multi-modal | arbitrary structure |
| Train cost | seconds | seconds | minutes (GPU-free OK) |
| MCU cost | ~µs, bytes | ~µs, KB | ms, tens–hundreds of KB |
| Today's role | **deploy on device** | notebook + emlearn option | notebook (concept) |

The notebook AE (65 k params ≈ 254 KB float32) claims **a quarter of our 1 MB flash** for weights alone — plus tens of kB of RAM for Conv1D activations. Size before you ship.

---

<!--
Switch to the deployable track: Edge Impulse anomaly block. Screenshot from the
old exercise (fresh 2026 UI). The block sits parallel to the classifier in the
same impulse — one deployment carries both.
-->

## 🧪 Lab track 1 — the three methods in notebooks (~40 min)

**`exercises/module8-anomaly/notebooks/`** — in order:

- `01_kmeans_anomaly.ipynb` → `02_gmm_anomaly.ipynb` → `03_autoencoder_anomaly.ipynb`
- All three use the same protocol: train on `normal` **only**, score everything
- Hold out one fault class entirely — does each method still catch it?
- **Done when:** you have three ROC-ish score plots and a favourite method

<!--
Notebook track lands here, right after the three methods and before the EI material — the concepts are freshest now, and the EI block section that follows becomes 'the deployable version of what you just built by hand'. The held-out-fault protocol is the intellectual core of the module: it simulates the fault nobody recorded.
-->

---

## Edge Impulse anomaly blocks

![w:900](../brightspace-export/_ontent/i39a275e2-29c7-45a0-b627-a4e30b2cc8db/Screenshot%202026-05-14%20at%2010.33.38.png)

- Add **Anomaly Detection (K-means)** as a *second* learning block in your Module 7 impulse
- Classifier and anomaly detector share the same DSP features
- One C++ export carries **both** — `result.classification[]` *and* `result.anomaly`

---

<!--
Axis selection: EI's K-means block asks which features to cluster on. Pick the
high-importance ones from the feature explorer (typically RMS and low-frequency
spectral power for imbalance). Fewer, well-chosen axes = tighter clusters =
better detection.
-->

## Configuring the block

- Select **which features** the K-means runs on — start from the feature-importance list (Module 5 intuition!)
- For the fan: RMS + spectral-power axes usually separate best
- Cluster count: default 32 is fine to start; fewer clusters = tighter "normal" definition
- **Train on `normal` (and `off`) data only** — remove fault classes from the anomaly training set
  <!-- VERIFY: current EI Studio UI — anomaly block trains on all data unless classes are filtered in the block settings -->

---

<!--
Verification before deployment, using EI live testing — screenshots from the
old exercise. Known motion → low anomaly score; unknown motion → high score.
We do the same with fan states: normal → low, scrape/worn fan → high.
-->

## Verify in the Studio first

Known state → classification confident, **anomaly score low**:

![w:700](../brightspace-export/_ontent/i39a275e2-29c7-45a0-b627-a4e30b2cc8db/Screenshot%202026-05-14%20at%2010.48.04.png)

---

<!--
Second half of the verification pair. In the lab: record the worn/faulty fan
(never in training) and watch the score jump. Emphasise: this screenshot pair
is gesture data from the old course — same workflow, different signal.
-->

## …then show it something new

Unknown state → **anomaly score jumps**:

![w:700](../brightspace-export/_ontent/i39a275e2-29c7-45a0-b627-a4e30b2cc8db/Screenshot%202026-05-14%20at%2010.51.03.png)
<!-- TODO: screenshots show old gesture project — re-capture with the fan project for the final deck. Workflow identical. -->

Lab version: hold back one fault state (e.g. *scrape* or the worn fan) from **all** training, then replay it in *Live classification*.

---

<!--
The combined decision logic on device — anomaly score as a confidence gate in
front of the classifier. This is the pattern they should remember: never act on
a classification when the anomaly score says "we've never seen this".
-->

## On-device pattern: anomaly score as a gate

```cpp
run_classifier(&signal, &result, false);

if (result.anomaly > ANOMALY_THRESHOLD) {        // tune from Studio live tests
    Serial.printf("ANOMALY  score=%.2f  (classifier output suppressed)\n",
                  result.anomaly);
    digitalWrite(LED_BLUE, HIGH);                // unknown-state indicator
} else {
    print_best_class(&result);                   // trust the classifier
    digitalWrite(LED_BLUE, LOW);
}
```

- `result.anomaly` is populated automatically when the impulse has an anomaly block
- Threshold: start where Studio's live tests separated known/unknown, then tune on the rig

---

<!--
Where this goes in production. Fleet-level condition
monitoring is largely anomaly-first: baseline per installed pump, alert on
drift, classify only what you have labels for. Also mention scheduled
re-baselining after maintenance.
-->

## This is a live research field — MIMII

- **MIMII**: Sound Dataset for **Malfunctioning Industrial Machine** Investigation
- Real factory recordings: **fans**, pumps, valves, slide rails — normal + faulty
- The published baseline approach: train an **autoencoder on normal sound only** — exactly today's method 3

![w:640](assets/reddi/3-8-6-mimii-dataset.png)

<sub>Figure: TinyML on edX (HarvardX), V.J. Reddi et al. — used with permission · Dataset: Purohit et al., MIMII (CC BY-SA)</sub>

<!--
Your lab today is a miniature of a real research benchmark: MIMII contains industrial fans and pumps with normal and fault recordings, and the standard baseline is an autoencoder trained on normal data only — method 3 from an hour ago. If anyone wants homework: the dataset is CC BY-SA, downloadable tonight, and your Module 5 feature pipeline runs on it almost unchanged (it's audio, so think band energies at higher sample rates). ToyADMOS is the companion dataset — 540 hours of miniature-machine sounds.
-->

---

## From fan rig to plant floor

- Production condition monitoring is **anomaly-first**: every installation gets its own "normal" baseline
- Classifiers come second — they explain *known* faults; anomaly scores catch the rest
- Re-baseline after maintenance (new bearing = new normal)
- Trend the score, don't just threshold it: slow drift = wear, step change = event

---

<!--
Exercise hand-off, two tracks. Notebook track = understanding (K-means → GMM →
AE progression on fan features). Device track = the EI anomaly block extending
Module 7's project. Deliverable: a demo where the worn fan triggers the anomaly
LED while trained states classify normally.
-->

## 🧪 Lab track 2 — anomaly detection on the device

**`exercises/module8-anomaly/`** → Track 2
*(track 1 — the notebooks — ran after the three-methods section)*

- Add the K-means anomaly block to your Module 7 EI project
- Retrain on **normal-only**, redeploy the Arduino library
- Print `result.anomaly`, gate the classifier on it

**Done when:** the held-out fault lights the anomaly LED — while trained states still classify. Write your threshold + observed scores into the README table.

---

<!--
Bridge to Module 9: everything now on the device is float32. The anomaly-
gated classifier is the system we optimise next — quantisation and pruning,
measured with the same scoreboard discipline.
-->

## Bridge to Module 9

Your device now runs: **DSP features → classifier → anomaly gate** — all in float32.

Questions we have not asked yet:

- Does it *have* to be float32? (No.)
- What does int8 cost in accuracy — and buy in RAM/flash/latency?
- Are all those weights even *doing* anything? (Also no.)

**Next: Module 9 — quantisation & pruning. Same models, smaller & faster.**
