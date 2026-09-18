"""Opt-in local retrieval benchmark; never imports evaluation cases into the app.

Copies the existing corpus into uniquely named collections; never overwrites it.
Memory readings are Ollama resident allocation snapshots, not process peak RSS.
"""
import hashlib
import json
import statistics
import time
import uuid
from pathlib import Path

from ollama import Client
from qdrant_client import QdrantClient, models
from src.config import settings
from src.retrieval import rerank


CASES = [
    ("A grubunda kayıp kaçak hedefi en fazla yüzde kaç?", "Teblig", "MADDE 3"),
    ("C bölgesi için izin verilen kayıp oranı tavanını bul.", "Teblig", "MADDE 3"),
    ("Şebekeye giren ve faturalanan enerji farkının oranı nasıl tanımlanır?", "Teblig", "MADDE 2"),
    ("Kayıp kaçak yüzdesi hangi tarihe kadar Kurula bildirilmeli?", "Teblig", "MADDE 4"),
    ("Hatalı bildirim halinde idari para cezasının tutarı belirtilmiş mi?", "Teblig", "MADDE 5"),
    ("Gelir tavanından yapılabilecek kesintinin üst sınırı nedir?", "Teblig", "MADDE 3"),
    ("Elektrik sayaçlarının faydalı ömrü kaç sene?", "Yonetmelik", "MADDE 2"),
    ("SCADA sistemlerinde amortisman süresi nedir?", "Yonetmelik", "MADDE 2"),
    ("Bir yatırımın düzenlenmiş varlık tabanına kabul şartlarını bul.", "Yonetmelik", "MADDE 3"),
    ("Yatırım raporunda hangi hesapların yıl sonu mutabakatı istenir?", "Yonetmelik", "MADDE 4"),
    ("İkinci çeyrek mali tabloları en geç ne zaman sunulur?", "Genelge", "Giriş"),
    ("Finansman giderleri raporda hangi hesaplarda ayrı gösterilmeli?", "Genelge", "Giriş"),
]


def main():
    output = Path('review_artifacts/embedding_comparison_2026-09-16.json')
    qdrant = QdrantClient(host='127.0.0.1', port=6333, timeout=60)
    ollama = Client(host=settings.ollama_host, timeout=120)
    corpus, offset = [], None
    while True:
        points, offset = qdrant.scroll('epdk_mevzuat', limit=100, offset=offset, with_vectors=False)
        corpus.extend(p.payload for p in points)
        if offset is None:
            break
    corpus.sort(key=lambda p: (p['source'], p['section'], p['text']))
    if not corpus:
        raise RuntimeError('Source collection is empty')
    report = {'corpus_sha256': hashlib.sha256(json.dumps(corpus, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
              'chunks': len(corpus), 'models': [], 'method': 'Current application embedding API, unprefixed text, dense top20 plus existing lexical reranker. Single run; not a statistical quality estimate.',
              'memory_method': 'Ollama ps resident size/size_vram after indexing; not peak process RAM. Generalge is one existing chunk, so section precision cannot be measured there.'}

    def save():
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

    for name in ['nomic-embed-text', 'bge-m3']:
        collection = 'benchmark_' + name.replace('-', '_') + '_' + uuid.uuid4().hex[:10]
        result = {'model': name, 'collection': collection, 'cases': []}
        report['models'].append(result)
        save()
        start = time.perf_counter()
        vectors = []
        for chunk in corpus:
            vectors.append(ollama.embeddings(model=name, prompt=chunk['text'])['embedding'])
        result['index_embedding_seconds'] = round(time.perf_counter() - start, 3)
        result['dimension'] = len(vectors[0])
        result['resident_models'] = ollama.ps().model_dump(mode='json')
        qdrant.create_collection(collection, vectors_config=models.VectorParams(size=len(vectors[0]), distance=models.Distance.COSINE))
        qdrant.upsert(collection, points=[models.PointStruct(id=i, vector=v, payload=p) for i, (v, p) in enumerate(zip(vectors, corpus))], wait=True)
        for question, source, section in CASES:
            start = time.perf_counter()
            vector = ollama.embeddings(model=name, prompt=question)['embedding']
            hits = qdrant.query_points(collection, query=vector, limit=20).points
            candidates = [dict(h.payload, score=h.score) for h in hits]
            ranked = rerank(question, candidates, 8)
            def rank(items):
                return next((i for i, c in enumerate(items, 1) if source in c['source'] and c['section'].startswith(section)), None)
            result['cases'].append({'question': question, 'expected_source_fragment': source, 'expected_section': section,
                                    'dense_rank': rank(candidates), 'reranked_rank': rank(ranked),
                                    'seconds': round(time.perf_counter() - start, 3)})
            save()
        for field in ['dense_rank', 'reranked_rank']:
            result[field + '_top1'] = sum(c[field] == 1 for c in result['cases'])
            result[field + '_top3'] = sum(c[field] is not None and c[field] <= 3 for c in result['cases'])
        result['median_query_seconds'] = statistics.median(c['seconds'] for c in result['cases'])
        save()
        print(json.dumps({k: v for k, v in result.items() if k not in {'cases', 'resident_models'}}, ensure_ascii=False), flush=True)
    print(str(output), flush=True)


if __name__ == '__main__':
    main()
