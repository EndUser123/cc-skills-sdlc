import sys, json
from pathlib import Path
sys.path.insert(0, str(Path('scripts').resolve()))
from preflight_propose import generate_proposal

corpus = [json.loads(l) for l in Path('tests/fixtures/pi_suitability_corpus.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
print('FP (predicted=pi, label != pi):')
for row in corpus:
    p = generate_proposal(row['prompt'], 'r', 't')
    pred = p['model_affinity']
    intent = p.get('task_intent', '?')
    if pred == 'pi' and row['label'] != 'pi':
        print(f'  INTENT={intent:10} LABEL={row["label"]:7} | {row["prompt"][:70]}')
print()
print('FN (label=pi, predicted != pi):')
for row in corpus:
    p = generate_proposal(row['prompt'], 'r', 't')
    pred = p['model_affinity']
    intent = p.get('task_intent', '?')
    if row['label'] == 'pi' and pred != 'pi':
        print(f'  INTENT={intent:10} PRED={pred:7} | {row["prompt"][:70]}')
