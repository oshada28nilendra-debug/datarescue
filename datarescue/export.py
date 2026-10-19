"""Export a fixed trusted engine, never model-generated executable code."""

import json
from pathlib import Path


def standalone(recipe):
    root = Path(__file__).parent
    dataset = (root / "dataset.py").read_text(encoding="utf-8")
    engine = (root / "engine.py").read_text(encoding="utf-8")
    engine = engine.replace("from .dataset import Error, Table\n", "")
    return (
        "#!/usr/bin/env python3\n# DataRescue 0.1.0 · MIT · fixed deterministic engine, no model code.\n"
        + dataset
        + "\n"
        + engine
        + "\nRECIPE = json.loads("
        + repr(json.dumps(recipe, ensure_ascii=True))
        + ")\n"
        + """
if __name__ == '__main__':
    import argparse
    import sys
    parser = argparse.ArgumentParser(description='Replay an approved DataRescue recipe on the exact original CSV')
    parser.add_argument('input')
    parser.add_argument('output')
    args = parser.parse_args()
    try:
        table = load_csv(args.input)
        if table.source_sha256 != RECIPE['source_sha256']:
            raise Error('Input differs from the reviewed original. Generate a fresh preview.')
        for operation in RECIPE['operations']:
            table, _ = transform(table, operation)
        output = table.csv_bytes()
        if hashlib.sha256(output).hexdigest() != RECIPE['output_sha256']:
            raise Error('Replay output mismatch')
        with open(args.output, 'xb') as handle:
            handle.write(output)
        print('Replayed exact approved output:', RECIPE['output_sha256'])
    except (Error, OSError) as exc:
        print('Refused: ' + str(exc), file=sys.stderr)
        sys.exit(2)
"""
    )
