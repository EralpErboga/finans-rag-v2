"""Small, source-derived hybrid evidence; no question/answer fixtures."""
import re
from src.retrieval import terms


def restrict_context_plan(question, plan, catalog):
    """Explanatory conjunctions are not authorization to add unrelated accounts."""
    if plan.get("operation") not in {"sum", "lookup"}:
        return plan
    if re.search(r"\b\d{3}\b", question) or re.search(r"topla|oranla|farkını|böl", question.lower()):
        return plan
    by_id = {row["id"]: row for row in catalog}
    ids = plan.get("items", [])
    if not isinstance(ids, list) or any(item not in by_id for item in ids):
        raise ValueError("Geçersiz mali kalem seçimi")
    query_terms = set(terms(question))
    scores = {item: len(query_terms.intersection(terms(by_id[item]["label"]))) for item in ids}
    best = max(scores.values(), default=0)
    if not best:
        raise ValueError("Mali kalem soru ile doğrulanamadı")
    ids = [item for item in ids if scores[item] == best]
    # Farklı tablolardaki aynı kalemler alternatif kaynaklardır.
    preferred = "gelir_tablosu" if "gelir tablo" in question.lower() else "mizan"
    ids.sort(key=lambda item: by_id[item]["source"] != preferred)
    unique, seen = [], set()
    for item in ids:
        key = tuple(terms(by_id[item]["label"]))
        if key not in seen:
            unique.append(item)
            seen.add(key)
    return {"operation": "lookup", "items": unique}


def compact_contexts(contexts, word_budget=150):
    """Keep whole article paragraphs; never cut a statement mid-sentence."""
    excerpts, used = [], []
    remaining = word_budget
    articles = [context for context in contexts if re.match(r"madde\b", context["section"], re.I)]
    if articles:
        contexts = articles
    for context in contexts:
        lines = context["text"].splitlines()
        if lines and lines[0].strip() == context["section"].strip():
            lines = lines[1:]
        body = "\n".join(lines).strip()
        paragraphs = re.split(r"\n(?=\(\d+\))", body)
        selected = []
        for paragraph in paragraphs:
            words = len(paragraph.split())
            if words <= remaining:
                selected.append(paragraph)
                remaining -= words
        if selected:
            excerpts.append(context["section"] + "\n\n" + "\n\n".join(selected))
            used.append(context)
    return excerpts, used


def valid_comment(text, response):
    return (bool(text) and len(text.split()) <= 90 and text.rstrip().endswith((".", "!", "?"))
            and response.get("done_reason") != "length"
            and not re.search(r"\d|[\u4e00-\u9fff\u0400-\u04ff]", text)
            and not re.search(r"kesin olarak|hedef.{0,20}aşılmıştır|uygundur|koşullar sağlanmıştır", text.lower())
            and bool(re.search(r"eksik|doğrulan|hesaplanamaz|belirlenemez|yetersiz", text.lower())))
