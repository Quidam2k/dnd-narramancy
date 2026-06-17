"""Side-by-side comparison of two narramancy JSONs for the same creature.

Usage:
    python scripts/ab_compare.py output/bael-narramancy.json output/haiku/bael-narramancy.json \
        --label-a gemma-4-12b --label-b claude-haiku-4-5 [--samples 6] [--out compare.md]
"""

import argparse
import json
import re
from collections import Counter
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def stats(data):
    entries = [e for t in data['tables'] for e in t['entries']]
    words = [w.lower() for e in entries for w in re.findall(r"[a-z']+", e.lower())]
    word_counts = [len(e.split()) for e in entries]
    vocab = len(set(words))
    # repetitiveness: share of entries starting with the same first word as another entry
    first_words = Counter(e.split()[0].lower().strip('"') for e in entries if e.split())
    top_openers = first_words.most_common(5)
    return {
        'tables': len(data['tables']),
        'entries': len(entries),
        'avg_words': sum(word_counts) / len(word_counts),
        'vocab': vocab,
        'vocab_per_100_words': 100 * vocab / len(words),
        'top_openers': top_openers,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('file_a')
    p.add_argument('file_b')
    p.add_argument('--label-a', default='A')
    p.add_argument('--label-b', default='B')
    p.add_argument('--samples', type=int, default=6)
    p.add_argument('--out', default=None)
    args = p.parse_args()

    a, b = load(args.file_a), load(args.file_b)
    sa, sb = stats(a), stats(b)

    lines = [f"# A/B: {args.label_a} vs {args.label_b} — {a['creature']['name']}", '']
    lines.append(f"| metric | {args.label_a} | {args.label_b} |")
    lines.append('|---|---|---|')
    lines.append(f"| tables | {sa['tables']} | {sb['tables']} |")
    lines.append(f"| entries | {sa['entries']} | {sb['entries']} |")
    lines.append(f"| avg words/entry | {sa['avg_words']:.1f} | {sb['avg_words']:.1f} |")
    lines.append(f"| distinct vocabulary | {sa['vocab']} | {sb['vocab']} |")
    lines.append(f"| vocab per 100 words | {sa['vocab_per_100_words']:.1f} | {sb['vocab_per_100_words']:.1f} |")
    fmt = lambda ops: ', '.join(f'{w}×{n}' for w, n in ops)
    lines.append(f"| top entry openers | {fmt(sa['top_openers'])} | {fmt(sb['top_openers'])} |")
    lines.append('')

    # Sample shared tables spread across categories
    index_b = {(t['ability'], t['category']): t for t in b['tables']}
    seen_cats = set()
    shown = 0
    for t in a['tables']:
        key = (t['ability'], t['category'])
        if key not in index_b or t['category'] in seen_cats:
            continue
        seen_cats.add(t['category'])
        tb = index_b[key]
        lines.append(f"## {t['ability']} — {t['category']}")
        lines.append('')
        lines.append(f"**{args.label_a}:**")
        for e in t['entries'][:3]:
            lines.append(f'- {e}')
        lines.append('')
        lines.append(f"**{args.label_b}:**")
        for e in tb['entries'][:3]:
            lines.append(f'- {e}')
        lines.append('')
        shown += 1
        if shown >= args.samples:
            break

    report = '\n'.join(lines)
    if args.out:
        Path(args.out).write_text(report, encoding='utf-8')
        print(f'written to {args.out}')
    else:
        print(report)


if __name__ == '__main__':
    main()
