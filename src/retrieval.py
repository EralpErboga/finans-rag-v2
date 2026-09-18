"""Small-corpus lexical reranking of dense candidates, without extra model memory."""
import math
import re
from collections import Counter
from src.conversation import normalize


STOP = set("bir bu şu için ile ve veya ne nedir kaç nasıl hangi mi mı mu mü olarak göre bizim nedir peki".split())


def terms(text):
    # Önek eşleşmesiyle yaygın Türkçe ekleri karşıla.
    return [w[:5] for w in re.findall(r"\w+", normalize(text)) if len(w) >= 3 and w not in STOP]


def rerank(query, candidates, limit):
    if not candidates:
        return []
    docs = [Counter(terms(c.get("text", ""))) for c in candidates]
    query_terms = set(terms(query))
    average = sum(sum(d.values()) for d in docs) / len(docs) or 1
    frequencies = {t: sum(t in d for d in docs) for t in query_terms}
    scores = []
    for doc in docs:
        length = sum(doc.values())
        score = 0.0
        for t in query_terms:
            count = doc[t]
            idf = math.log(1 + (len(docs) - frequencies[t] + .5) / (frequencies[t] + .5))
            score += idf * count * 2.2 / (count + 1.2 * (.25 + .75 * length / average))
        scores.append(score)
    maximum = max(scores) or 1
    ranked = sorted(enumerate(candidates), key=lambda pair:
                    .65 * scores[pair[0]] / maximum + .35 * pair[1].get("score", 0), reverse=True)
    return [candidate for _, candidate in ranked[:limit]]
