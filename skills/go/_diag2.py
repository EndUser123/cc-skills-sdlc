import sys, json
from pathlib import Path
sys.path.insert(0, str(Path('scripts').resolve()))
from preflight_propose import generate_proposal

corpus = [json.loads(l) for l in Path('tests/fixtures/pi_suitability_corpus.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
print('All pi-labeled prompts — full signals:')
for row in corpus:
    if row['label'] != 'pi':
        continue
    p = generate_proposal(row['prompt'], 'r', 't')
    print(f'  intent={p.get("task_intent"):10} tier={p.get("execution_tier"):24} hi_risk={p.get("risk_signals",{}).get("high_risk")} pred={p["model_affinity"]:7} | {row["prompt"][:60]}')
