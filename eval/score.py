import json
from collections import defaultdict
from pathlib import Path

from sanitas import detect

DATA = Path(__file__).parent / "data" / "ai4privacy-en-200.jsonl"

hit = gold_total = pred_total = 0
by_label = defaultdict(lambda: [0, 0])  # label -> [covered chars, total chars]

for line in DATA.open():
    record = json.loads(line)
    pred = {i for d in detect(record["text"]) for i in range(d.start, d.end)}
    gold = set()
    for span in record["spans"]:
        chars = set(range(span["start"], span["end"]))
        gold |= chars
        by_label[span["label"]][0] += len(chars & pred)
        by_label[span["label"]][1] += len(chars)
    hit += len(gold & pred)
    gold_total += len(gold)
    pred_total += len(pred)

print(f"recall     {hit / gold_total:.1%}")
print(f"precision  {hit / pred_total:.1%}")
rates = {label: c / t for label, (c, t) in by_label.items()}
for label, rate in sorted(rates.items(), key=lambda x: x[1]):
    print(f"  {label:<18} {rate:.1%}")
