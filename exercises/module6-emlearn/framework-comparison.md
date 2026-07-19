# Module 6 Worksheet — MCU ML Framework Comparison

Fill this in from the frameworks' **own documentation** (links below) — not from
the lecture slides. Where the docs are ambiguous, write what you found *and*
where you found it. We reconcile everyone's tables in the module wrap-up.

Time budget: ~20 min. Split the four frameworks between you and your lab partner.

## The table

| Criterion | Edge Impulse | emlearn | AIfES | TFLite-Micro |
|---|---|---|---|---|
| Licence (of what you ship in firmware) | | | | |
| Cost model (free tier? commercial use?) | | | | |
| Where does training run? | | | | |
| On-device training possible? | | | | |
| Model types supported | | | | |
| Feature/DSP tooling included? | | | | |
| Smallest realistic footprint (flash) | | | | |
| RAM overhead beyond the model itself | | | | |
| How does a model get into your firmware? (header / library / FlatBuffer / cloud export) | | | | |
| Where does your *data* live during development? | | | | |
| Vendor lock-in: what would migrating away cost? | | | | |
| Maintained by / bus factor | | | | |

## Doc links

- Edge Impulse: https://docs.edgeimpulse.com — check the licence file inside a C++ deployment export, and the pricing page
- emlearn: https://emlearn.readthedocs.io + https://github.com/emlearn/emlearn (LICENSE)
- AIfES: https://github.com/Fraunhofer-IMS/AIfES_for_Arduino (LICENSE + README licensing section)
- TFLite-Micro: https://github.com/tensorflow/tflite-micro <!-- VERIFY: check for LiteRT rename before class -->

## Judgement questions (short answers)

1. You are building a **commercial pump-monitoring product** in closed-source
   firmware. Which framework(s) can you use without buying a licence or opening
   your source? Which require a conversation with legal?

2. Your model is a **Random Forest on 12 features**. Rank the four frameworks
   by how naturally they support this. (Hint: one of them can't, directly.)

3. Your product must **adapt its baseline to each installation** after
   deployment, without cloud connectivity. Which framework is designed for
   exactly this?

4. The vendor of your chosen SaaS pipeline **triples its prices** two years
   into your product's life. Walk through your exit: what do you still have
   (data? features? model? DSP config?), and what do you rebuild?

5. For **this course's fan classifier** (5 classes, ~20 features, nRF52840):
   which framework would you pick, and what is your second choice? One sentence
   of justification each.

## Reconciliation notes (fill during wrap-up)

- Rows where the class disagreed:
- Claims we could not verify from the docs:
- Updates vs the lecture's table (docs change faster than slides):
