"""Explicit live evaluation; preserve the historical stress report unchanged."""
import argparse
import hashlib
import json
import time
from pathlib import Path
from src.chains import RAGPipeline
from stress_test_20260916 import QUESTIONS, EXPECTATIONS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--end', type=int, default=12)
    parser.add_argument('--output', default='review_artifacts/accuracy_20260917.json')
    args = parser.parse_args()
    path = Path(args.output)
    rows = json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
    history = []
    for row in rows:
        history.extend(row['messages'])
    pipeline = RAGPipeline()
    for i in range(len(rows), args.end):
        started = time.perf_counter()
        result = pipeline.ask(QUESTIONS[i], [] if i == 29 else history)
        messages = [{'role': 'user', 'content': QUESTIONS[i]},
                    {'role': 'assistant', 'content': result['answer'], 'badge': result['type'],
                     **{key: result[key] for key in ['sources', 'finance_views', 'history_result', 'domain_context'] if key in result}}]
        rows.append({'id': i+1, 'question': QUESTIONS[i], 'expected': EXPECTATIONS[i],
                     'seconds': round(time.perf_counter()-started, 2), 'result': result, 'messages': messages,
                     'source_hashes': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('src').glob('*.py')}})
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
        history.extend(messages)
        print(json.dumps({'id': i+1, 'question': QUESTIONS[i], 'result': result}, ensure_ascii=False), flush=True)
        if result['type'] == 'ERROR':
            break


if __name__ == '__main__':
    main()
