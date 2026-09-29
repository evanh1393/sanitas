# Data

Every dataset used, where it came from, and its license. Only public or synthetic data.

| Dataset | Source | License | Used for |
| --- | --- | --- | --- |
| ai4privacy `openpii-masking-mini-10k` | [Hugging Face](https://huggingface.co/datasets/ai4privacy/openpii-masking-mini-10k) | [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/) | Scoring redaction |
| Synthetic records | Generated with Faker | n/a | Realistic documents with known planted PII |
| Enron email corpus | TBD | TBD | Messy real-world text |
| CFPB complaint narratives | consumerfinance.gov | TBD | Messy real-world text |

## ai4privacy sample

`eval/data/ai4privacy-en-200.jsonl`: 200 English records from the train split of
[openpii-masking-mini-10k](https://huggingface.co/datasets/ai4privacy/openpii-masking-mini-10k)
by ai4privacy, licensed CC-BY-4.0.

Changes: English rows only, random sample (seed 42), kept `uid`, `source_text` (as `text`)
and `privacy_mask` (as `spans`). All records are synthetic.

Regenerate:

    uv run --with datasets scripts/sample_ai4privacy.py
