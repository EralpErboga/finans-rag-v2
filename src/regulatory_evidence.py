"""Select labelled numeric provisions from retrieved text, without domain answer tables."""
import re
from src.conversation import normalize
from src.retrieval import terms


def numeric_values(text):
    return re.findall(r"%?\d+(?:[.,]\d+)*", text)


def condition_compatible(question, evidence):
    late = r'gecik|geç (?:sun|ver|bildir)|süresinde (?:sunulma|verilme|bildirilme)'
    return not re.search(late, normalize(question)) or bool(re.search(late, normalize(evidence)))


def evidence_passages(contexts):
    """Preserve headings, list items and wrapped paragraphs from retrieved documents."""
    passages = []
    for context in contexts:
        pending = []
        for line in context['text'].splitlines() + ['']:
            line = line.strip()
            boundary = not line or re.match(r'^(?:[-•]|\([0-9]+\)|[a-zçğıöşü]\)|[0-9]+\.)\s*', line)
            if boundary and pending:
                passages.append({'text': ' '.join(pending), 'context': context})
                pending = []
            if line:
                pending.append(line)
        if pending:
            passages.append({'text': ' '.join(pending), 'context': context})
    return passages


def unknown_letter_target(target, contexts):
    requested = {word for word in re.findall(r"\w+", normalize(target))
                 if len(word) == 1 and word.isalpha()}
    available = set()
    for context in contexts:
        for line in context["text"].splitlines():
            line = re.sub(r"^\s*(?:[a-zçğıöşü]|\d+)[).]\s*", "", line.strip(), flags=re.I)
            if ":" in line and numeric_values(line.split(":", 1)[1]):
                available.update(word for word in re.findall(r"\w+", normalize(line.split(":", 1)[0]))
                                 if len(word) == 1 and word.isalpha())
    return bool(requested and available and not requested.issubset(available))


def focused_provisions(target, contexts, question=None):
    if question:
        # Yalnızca ad eşleşmesine bakarak soruyu süre sorgusu sayma.
        filtered = []
        for context in contexts:
            labelled_lines = [line for line in context["text"].splitlines()
                              if ":" in line and numeric_values(line.split(":", 1)[1])]
            label_terms = {term for line in labelled_lines for term in terms(line.split(":", 1)[0])}
            requested_property = set(terms(question)) - label_terms
            preamble = context["section"] + " " + " ".join(
                line for line in context["text"].splitlines() if line not in labelled_lines)
            if not requested_property or requested_property.intersection(terms(preamble)):
                filtered.append(context)
        contexts = filtered
    parts = re.split(r"\s+(?:ve|ile)\s+|[,;]", target, flags=re.I)
    if len(parts) > 1:
        combined = []
        for part in parts:
            for row in focused_provisions(part, contexts):
                if row not in combined:
                    combined.append(row)
        return combined
    query_terms = set(terms(target))
    letters = {w for w in re.findall(r"\w+", normalize(target)) if len(w) == 1 and w.isalpha()}
    candidates = []
    seen = set()
    for context in contexts:
        for line in context["text"].splitlines():
            line = re.sub(r"^\s*(?:[a-zçğıöşü]|\d+)[).]\s*", "", line.strip(), flags=re.I)
            if ":" not in line:
                continue
            label, value = (part.strip() for part in line.split(":", 1))
            if not numeric_values(value) or not label or len(label) > 120:
                continue
            label_letters = {w for w in re.findall(r"\w+", normalize(label)) if len(w) == 1}
            if letters and label_letters and not letters.intersection(label_letters):
                continue
            overlap = len(query_terms.intersection(terms(label)))
            overlap += 3 * len(letters.intersection(label_letters))
            if not overlap:
                continue
            key = (context["source"], context["section"], label, value)
            if key in seen:
                continue
            seen.add(key)
            candidates.append({"label": label, "value": value.rstrip(",.;"),
                               "context": context, "overlap": overlap})
    if not candidates:
        return []
    # Daha özel bir etiket eşleştiğinde zayıf ortak sözcükleri ele.
    best = max(row["overlap"] for row in candidates)
    return [row for row in candidates if row["overlap"] == best]


def complete_grounded_answer(answer, provisions):
    """Check label/value association, not just presence of numbers anywhere."""
    if not answer or re.search(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af\u0400-\u04ff]", answer):
        return False
    allowed = {n for row in provisions for n in numeric_values(row["value"])}
    if re.search(r"değil|bulunma|bilgi verilme", normalize(answer)):
        return False
    if not set(numeric_values(answer)).issubset(allowed):
        return False
    sentences = re.split(r"[\n;]|(?<=[.!?])\s+", answer)
    for row in provisions:
        label_terms = set(terms(row["label"]))
        label_letters = {w for w in re.findall(r"\w+", normalize(row["label"])) if len(w) == 1}
        numbers = set(numeric_values(row["value"]))
        matched = False
        for sentence in sentences:
            sentence_words = set(re.findall(r"\w+", normalize(sentence)))
            if (label_terms.issubset(set(terms(sentence))) and label_letters.issubset(sentence_words)
                    and numbers == set(numeric_values(sentence))
                    and {w[:5] for w in re.findall(r"[^\W\d_]+", normalize(row["value"]))}.issubset(
                        {w[:5] for w in re.findall(r"[^\W\d_]+", normalize(sentence))})):
                matched = True
                break
        if not matched:
            return False
    return True
