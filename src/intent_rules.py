"""Task semantics and catalogue relationships, without evaluation question fixtures."""
import re
from src.conversation import normalize
from src.retrieval import terms


def history_request(text):
    return bool(re.search(r'sor(?:u|um|du)|mesaj|kelime|sözc|geçmiş|konuşt|dedim', normalize(text)))


def literal_history_request(text):
    return bool(re.search(r'mesaj|kelime|sözc|geçmiş|konuşt|dedim|ne sordum|ne sormuştum|sorularım|sorum ne', normalize(text)))


def question_features(text):
    value = normalize(text)
    return {name for name, pattern in {
        'amortization': r'amorti|faydalı öm',
        'reporting': r'rapor|takvim|çeyrek|bildir|gönder',
        'maintenance': r'bakım|periyodik|kalibrasyon',
        'scope': r'kapsam|kasted|hangi varlık',
        'balance': r'bakiye|tutar',
    }.items() if re.search(pattern, value)}


def independent_request(text):
    value = normalize(text)
    if re.search(r'\b\d{3}\b', value):
        return True
    reference = re.search(r'^(?:peki\s+)?(?:bu|bunu|bunun|bunlar\w*|aynı|iki\s+(?:kalem|görünüm)|az önce)\b', value)
    return not reference and bool(re.search(
        r'\?|\b(ne|nedir|neler|kaç|nasıl|hangi\w*|neden|mi|mı)\b|\b\d{3}\b|'
        r'göster|öğrenmek|istiyorum|söyle|karşılaştır|hesapla|geçelim|değil', value))


def route_contract(text, intent):
    value = normalize(text)
    regulatory = bool(re.search(
        r'mevzuat|tebliğ|yönetmelik|düzenlenmiş|\bdvt\b|kayıp.kaçak|kayıp oran|'
        r'faydalı öm|\bamorti\b|amortisman.*(?:süre|yıl)|hedef|üst sınır|kuruma|yasal|'
        r'raporla|çeyrek|takvim|gönder|bakım aralı|periyodik|uygunluk|varlık taban|'
        r'işletmeye alın|ceza|yükümlülük|denetlem|(?:hangi|son|aynı) ay|bildirim zamanı', value))
    financial = bool(re.search(
        r'bakiye|tutar|\btl\b|kaç lira|tablom|hesabımız|hesaplarımız|yatırımlarımız|'
        r'sermaye|özkaynak|kâr|karları|alacağ|alacaklarımız|gider|nakit|maliyet|'
        r'masraf|kazanç|tahsil|gelir tablom|gelirimiz|geliri|kayıtlarımız|kayıtlarda|\b\d{3}\b', value))
    # Raporlama kurallarına ilişkin soruları bakiye sorgusundan ayır.
    normative = bool(re.search(r'gönder|çeyrek|takvim|denetlem|raporlama|son ay', value))
    amount = bool(re.search(r'bakiye|tutar|\btl\b|kaç lira|ne kadar', value))
    if intent == 'CHAT_META' and literal_history_request(text):
        return intent
    if regulatory:
        company = bool(re.search(r'\b\d{3}\b|kayıt|bizim|şirket|tablom|hesab|yatırımımız|yatırımlarımız|bölgemiz', value))
        return 'HYBRID' if financial and company and (not normative or amount) else 'MEVZUAT'
    if financial:
        return 'FINANCE'
    if intent == 'HYBRID':
        return 'MEVZUAT'
    return intent


def gross_net_requested(text):
    value = normalize(text)
    return (bool(re.search(r'brüt', value) and re.search(r'net', value)) or
            bool(re.search(r'(?:karşılık|indirim|düşül|düşmeden)', value) and
                 re.search(r'önce|sonra|düşülmeden|düşüldükten', value)))


def catalogue_pairs(catalog):
    pairs = []
    for net in catalog:
        if net.get('source') != 'bilanco' or not re.search(r'\(net\)', net.get('label', ''), re.I):
            continue
        base = set(terms(re.sub(r'\(net\)', '', net['label'], flags=re.I)))
        gross = []
        for item in catalog:
            label = item.get('label', '')
            aliases = [re.sub(r'\([^)]*\)', '', label), *re.findall(r'\(([^)]*)\)', label)]
            if (item.get('source') == 'mizan' and '(-)' not in label and base and
                    any(set(terms(alias)) == base for alias in aliases)):
                gross.append(item['id'])
        if len(gross) == 1:
            pairs.append((gross[0], net['id']))
    return pairs
