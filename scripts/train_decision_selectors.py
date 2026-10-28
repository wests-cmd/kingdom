"""Dependency-free contrastive training for isolated low-memory model labs.

No upstream Nimble code or weights. Synthetic labels teach resource preferences;
held-out policy imitation is not evidence of faster real-world execution.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import resource
import time

FEATURES = ['fit', 'local', 'idle', 'memory_headroom', 'success', 'latency', 'load']
POLICIES = {'model': [4., 2., 1., 1., 3., -1., -1.],
            'knight': [3., 0., 3., 2., 3., -1., -3.]}


def examples(seed, count, policy):
    rng = random.Random(seed)
    for pair in range(count):
        left = [rng.random() for _ in FEATURES]
        right = list(left)
        # One changed fact per pair makes the intended policy inspectable.
        index = rng.randrange(len(FEATURES))
        right[index] = rng.random()
        if pair % 2:
            right = [rng.random() for _ in FEATURES]
        difference = [a-b for a, b in zip(left, right)]
        score = sum(a*b for a, b in zip(policy, difference))
        if abs(score) > .01:
            yield difference, int(score > 0)


def train(destination):
    start = time.perf_counter()
    destination.mkdir(parents=True, exist_ok=True)
    receipt = {'schema': 1, 'label_source': 'synthetic resource policy',
               'not_proven': ['real-job speedup', 'semantic task quality', 'end-to-end autonomy'],
               'models': {}}
    for kind, policy in POLICIES.items():
        weights = [0.] * len(FEATURES)
        training = list(examples(907, 6000, policy))
        for _ in range(15):
            for difference, label in training:
                score = max(-30., min(30., sum(w*x for w, x in zip(weights, difference))))
                error = label - 1/(1+math.exp(-score))
                weights = [w + .08*(error*x - .0001*w) for w, x in zip(weights, difference)]
        held_out = list(examples(1937, 2000, policy))
        correct = sum((sum(w*x for w, x in zip(weights, difference)) > 0) == bool(label)
                      for difference, label in held_out)
        rng = random.Random(7811)
        multi = [[rng.uniform(-1, 1) for _ in FEATURES] for _ in range(2000)]
        multi_accuracy = sum((sum(w*x for w, x in zip(weights, row)) > 0) ==
                             (sum(w*x for w, x in zip(policy, row)) > 0) for row in multi)/len(multi)
        artifact = {'schema': 1, 'kind': kind, 'features': FEATURES, 'weights': weights,
                    'mode': 'shadow', 'training': {'pairs': len(training), 'seed': 907,
                    'labels': 'synthetic resource policy', 'held_out_seed': 1937,
                    'held_out_pairs': len(held_out), 'policy_pair_accuracy': correct/len(held_out),
                    'multi_fact_pairs': len(multi), 'multi_fact_policy_accuracy': multi_accuracy}}
        path = destination / (kind + '.json')
        path.write_text(json.dumps(artifact, indent=2)+'\n', encoding='utf-8')
        canonical = json.dumps(artifact, sort_keys=True, separators=(',', ':')).encode('utf-8')
        receipt['models'][kind] = {'sha256': hashlib.sha256(canonical).hexdigest(), 'hash_encoding': 'canonical-json-v1',
                                  'bytes': path.stat().st_size, **artifact['training']}
    receipt['seconds'] = time.perf_counter() - start
    receipt['peak_rss_kib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    (destination/'training-receipt.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(receipt))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    train(parser.parse_args().output)
