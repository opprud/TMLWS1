# Module 1 Lab — ML Basics in Jupyter/Colab

Four exercises, in order. Everything runs in **Google Colab** (zero install, needs a Google account) or locally in Jupyter using the `tinyml-env` from the [setup guide](../../setup-guide.md). Budget ~90 min; exercise 4 is optional if time runs short.

| # | Exercise | Tool | ~Time |
|---|---|---|---|
| 1 | Pandas warm-up | pandas/matplotlib | 20 min |
| 2 | House prices — Keras MLP regression | Keras | 25 min |
| 3 | MNIST — dense NN classifier | Keras | 25 min |
| 4 | CIFAR-10 — CNN teaser (optional) | Keras | 20 min |

---

## Exercise 1 — Introduction to pandas

Pandas is the Python library for tabular data — DataFrames are spreadsheets you can program. You will use it constantly in this course: every sensor recording you make ends up in a DataFrame for sanity-checking before it goes near a model.

The two structures to know:

- **Series** — a 1-D labelled array (one column)
- **DataFrame** — a 2-D table (rows × columns); filtering, grouping, plotting, joins — Excel with a REPL

### Steps

1. New to numpy? Run this first: [Introduction to NumPy (Colab)](https://colab.research.google.com/github/ageron/handson-ml3/blob/main/tools_numpy.ipynb)
2. Run the [Pandas introduction (Colab)](https://colab.research.google.com/github/ageron/handson-ml3/blob/main/tools_pandas.ipynb)
3. Optional: [Matplotlib introduction (Colab)](https://colab.research.google.com/github/ageron/handson-ml3/blob/main/tools_matplotlib.ipynb)

### Work with real accelerometer data

In Module 3 you will record your own CSVs — bookmark this section and repeat it then. For now, grab any 3-axis accelerometer CSV (ask the instructor for a sample with columns `timestamp,accX,accY,accZ`) and:

1. Load it: `df = pd.read_csv("circle.1.csv")`
2. Run `df.describe()` —
   - What are the min/max values? How do they correspond to the sensor's g-range (±4 g ≈ ±39.2 m/s²)?
   - What is the average value per axis? (Hint: at rest, gravity ≈ 9.81 m/s² shows on exactly one axis.)
3. Plot x, y, z as a line plot: `df.plot()`
4. Pick a threshold (e.g. ⅔ of the max amplitude), draw it with `plt.axhline(...)`, and count how many samples exceed it (`(df["accX"] > thr).sum()`)
5. Plot a histogram (`df.hist(bins=...)`) —
   - How many bins do you need before the shape is visible?
   - Is the data Gaussian, or something else? Why might a gesture *not* be Gaussian?

**Expected output (circle recording):** 
**Expected output (idle recording):** `describe()` shows means near `(0, 0, 9.8)` and std well below 1 m/s²; the plot is three nearly flat lines.

---

## Exercise 2 — Predict house prices (Keras MLP regression)

First contact with Keras: a two-layer Multi-Layer Perceptron predicting house prices from tabular features. We jump straight in *before* discussing hyperparameters in depth — the goal is to see the workflow end to end.

> **Dataset note:** the old version of this exercise used the **Boston housing** dataset (506 samples, 13 features). It has been **removed from scikit-learn and Keras** because one of its features (`B`) encodes racial composition — a textbook example of why you should know what's *in* your dataset. We use its standard replacement, **California housing**: 20,640 samples, 8 features (median income, house age, average rooms, latitude/longitude, …), target = median house value.

### Steps

1. Open a fresh Colab/Jupyter notebook and build the model yourself (this is deliberate — it's ~20 lines):

   ```python
   from sklearn.datasets import fetch_california_housing
   from sklearn.model_selection import train_test_split
   from sklearn.preprocessing import StandardScaler
   from tensorflow import keras

   X, y = fetch_california_housing(return_X_y=True)
   X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

   scaler = StandardScaler()
   X_train = scaler.fit_transform(X_train)
   X_test  = scaler.transform(X_test)          # note: fit on train only!

   model = keras.Sequential([
       keras.layers.Input(shape=(8,)),
       keras.layers.Dense(64, activation="relu"),
       keras.layers.Dense(64, activation="relu"),
       keras.layers.Dense(1),
   ])
   model.compile(optimizer="adam", loss="mse", metrics=["mae"])
   history = model.fit(X_train, y_train, epochs=50,
                       validation_split=0.2, verbose=1)
   print(model.evaluate(X_test, y_test))
   ```

2. Plot `history.history["loss"]` and `history.history["val_loss"]` on one figure.
3. Predict a few test samples and compare with the true values.

**Expected output:** test MAE around **0.35–0.45** (target is in units of $100k, so the model is off by roughly $35–45k on average). Training takes < 2 min on Colab CPU.

### Observe & discuss

- What is the difference between MAE and RMSE — and what is the purpose of the error (loss) function?
- What is the shape of the input data fed through the network?
- How many epochs do you train for? After how many epochs does the network stop improving *significantly*?
- What happens to `val_loss` if you train for 500 epochs? (Name the phenomenon.)
- Why is the `StandardScaler` fitted on the training set only?

---

## Exercise 3 — Predict handwritten digits (MNIST, dense NN)

Build a classifier that recognises handwritten digits — 28×28-pixel grayscale images, 10 classes. The compute needed to *run* this model is well within reach of the microcontroller in your kit.

**MNIST facts:** 70,000 images (60k train / 10k test) of digits written by many different people; the "Hello World" benchmark of image classification. The model here is a two-layer dense network with ~16k parameters.

Contrast this with Exercise 2: there, humans engineered the features (rooms, income, …). Here the input is **raw pixels** — all the reasoning about content is left to the network. No human intuition used. Remember this trade-off; it returns on Day 2 when we choose between hand-crafted features and raw-signal models on the fan.

### Steps

1. Run the Colab: [TF_MNIST_Classification_v2.ipynb (UNIFEI-IESTI01)](https://colab.research.google.com/github/Mjrovai/UNIFEI-IESTI01-TinyML-2022.1/blob/main/00_Curse_Folder/1_Fundamentals/Class_09/TF_MNIST_Classification_v2.ipynb)
   *(or download it and run locally: File → Download → Download .ipynb)*
2. Train the model as given; note the test accuracy.
3. **Break it on purpose:** re-train with the learning rate ×10, then ÷100. Watch the loss curves.
4. Generate the confusion matrix cell. Which digit pairs get confused? Do the mistakes look human?
5. Download the trained `.h5` model file and open it in [Netron](https://netron.app/) — inspect layers, shapes, and parameter counts.

**Expected output:** test accuracy ≈ **97–98%** after a few epochs. LR ×10: loss jumps around or explodes. LR ÷100: loss decreases painfully slowly.

### Observe & discuss

- What happens when you adjust the learning rate up or down before training?
- What is the purpose of a confusion matrix — what does it show that accuracy hides?
- In Netron: where do the ~16k parameters come from? Verify with the formula `inputs × outputs + outputs`.

---

## Exercise 4 — Classify photos with a CNN (CIFAR-10) *(optional teaser)*

CIFAR-10: 60,000 **colour** images, 32×32 px, 10 classes (airplane, car, bird, cat, …). Harder than MNIST: colour channels, varied backgrounds, real objects. Dense layers alone struggle here — this is where **convolutional** layers earn their keep by exploiting spatial structure with far fewer parameters.

### Steps

1. Run the Colab: [CNN_Cifar_10.ipynb (UNIFEI-IESTI01)](https://colab.research.google.com/github/Mjrovai/UNIFEI-IESTI01-TinyML-2022.1/blob/main/00_Curse_Folder/1_Fundamentals/Class_11/CNN_Cifar_10.ipynb)
2. Train for a handful of epochs (full training takes a while — Colab GPU runtime recommended: Runtime → Change runtime type → GPU).

### Observe & discuss

- What shape does the input data have now — pixels, channels?
- What is the purpose of the convolution and pooling layers?
- How many epochs until accuracy is "good"? What *is* a good accuracy, to you?
- What is an activation function, and how is ReLU implemented? (One line of C. Write it.)

**Expected output:** ~65–70% test accuracy after ~10 epochs. (State of the art is >99% — and needs millions of parameters. We will care about the other end of that curve.)

> On Day 3 we build a 1-D CNN on raw vibration windows — same idea as this exercise, one dimension fewer, and small enough to run on your RAK4631.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Colab: "Cannot connect to runtime" | Runtime → Reconnect; or copy the notebook to your Drive (File → Save a copy) |
| Colab session reset, lost variables | Runtime → Run all — notebooks are built to re-run top to bottom |
| Local: `No module named tensorflow` | activate the env: `source ~/tinyml-env/bin/activate`; TF missing? `pip install tensorflow` |
| Local: TF install too heavy / fails | just use Colab — that's why it's the default here |
| `fetch_california_housing` fails with `CERTIFICATE_VERIFY_FAILED` | macOS python.org build has no default CA bundle. The notebook's cert-fix cell (points Python at `certifi`) handles it; if running your own script, either run **`/Applications/Python 3.11/Install Certificates.command`** once, or `export SSL_CERT_FILE=$(python -c "import certifi;print(certifi.where())")`. |
| `fetch_california_housing` download error (other) | corporate proxy/firewall — run that exercise in Colab |
| Training absurdly slow on CIFAR | enable the GPU runtime (see Exercise 4), or reduce epochs |
| External Colab link dead (UNIFEI repo) | mirrored copies: ask instructor / check the course repo `notebooks/` folder |
