import json

from datasets import load_dataset

ds = load_dataset("ai4privacy/openpii-masking-mini-10k", split="train")
en = ds.filter(lambda r: r["language"] == "en")
sample = en.shuffle(seed=42).select(range(200))

with open("eval/data/ai4privacy-en-200.jsonl", "w") as f:
    f.writelines(
        json.dumps(
            {"uid": r["uid"], "text": r["source_text"], "spans": r["privacy_mask"]}
        )
        + "\n"
        for r in sample
    )
