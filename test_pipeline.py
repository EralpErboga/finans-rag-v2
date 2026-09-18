"""Canlı Ollama + Qdrant + SQLite kabul testleri: python test_pipeline.py.

Beklenen tutarlar ve oranlar projedeki 2024 dummy veri setine aittir.
Herhangi bir senaryonun başarısızlığı süreci sıfırdan farklı kodla sonlandırır.
"""

import math
import re
from time import perf_counter


def check_finance(result, expected_amount):
    assert result.get("type") == "FINANCE", f"Finans kanalı bekleniyordu: {result}"
    raw = result.get("raw_data", {})
    assert raw.get("status") == "success", f"Mali sorgu planı başarısız: {raw}"
    rows = raw.get("data", [])
    assert len(rows) == 1, f"Tek toplam satırı bekleniyordu: {rows}"
    values = [
        value for value in rows[0].values()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    ]
    assert len(values) == 1, f"Tek sayısal toplam bekleniyordu: {rows}"
    assert math.isclose(values[0], expected_amount, rel_tol=0, abs_tol=0.01), (
        f"Beklenen tutar {expected_amount}, SQL sonucu {values[0]}"
    )
    formatted = f"{expected_amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    answer = result.get("answer", "")
    assert re.search(r"(?<![-\d])" + re.escape(formatted) + r"\s*TL\b", answer), (
        f"Yanıt doğrulanan {formatted} TL tutarını korumuyor: {answer}"
    )
    assert result.get("sources"), f"Finans yanıtında kaynak bulunamadı: {result}"


def check_mevzuat(result):
    assert result.get("type") == "MEVZUAT", f"Mevzuat kanalı bekleniyordu: {result}"
    answer = result.get("answer", "")
    assert re.search(r"%\s*8(?:[.,]0+)?(?!\d|[.,]\d)", answer), (
        f"Dummy A grubu sınırı %8 yanıt içinde bulunamadı: {answer}"
    )
    assert not re.search(r"%\s*8[.,]5", answer), f"Eski yanlış %8,5 değeri tekrarlandı: {answer}"
    sources = result.get("sources", [])
    cited_articles = [
        source for source in sources
        if source.get("source") == "EPDK_Ornek_Teblig_Kayip_Kacak_2024.txt"
        and re.search(r"MADDE\s+3\b", source.get("section", ""), re.IGNORECASE)
    ]
    assert cited_articles, f"Kayıp-kaçak Tebliği Madde 3 kaynaklarda bulunamadı: {sources}"
    assert any(
        re.search(r"A\s+Grubu[^\n]*%\s*8(?!\d|[.,]\d)", source.get("text", ""), re.IGNORECASE)
        for source in cited_articles
    ), "Gösterilen Madde 3 kaynağı beklenen A grubu %8 hükmünü içermiyor."


def check_out_of_scope(result):
    assert result.get("type") == "OUT_OF_SCOPE", f"Kapsam dışı kararı bekleniyordu: {result}"
    answer = result.get("answer", "")
    assert "EPDK" in answer and "finans" in answer.casefold(), (
        f"Yanıt uygulamanın kapsamını açıklamıyor: {answer}"
    )
    assert not result.get("sources"), "Hava durumu için mevzuat kaynağı üretilmemeli."
    assert not result.get("raw_data"), "Hava durumu için finansal veri üretilmemeli."


def run_pipeline_test():
    from src.chains import RAGPipeline

    print("Canlı kabul testleri başlatılıyor (Ollama ve Qdrant açık olmalı)...", flush=True)
    pipeline = RAGPipeline()
    print(f"Model: {pipeline.llm_model}", flush=True)
    cases = [
        ("Kasa", "Kasa hesabının bakiyesi ne kadar?", lambda result: check_finance(result, 270_000)),
        ("A grubu mevzuatı", "A grubu bölgelerde kayıp-kaçak hedef üst sınırı nedir?", check_mevzuat),
        (
            "Genel yönetim giderleri",
            "Genel yönetim giderlerimiz ne kadar?",
            lambda result: check_finance(result, 21_200_000),
        ),
        ("Kapsam dışı", "Yarın Samsun'da hava durumu nasıl olacak?", check_out_of_scope),
    ]
    failures = []
    total_start = perf_counter()
    for name, question, verify in cases:
        started = perf_counter()
        print(f"\n[{name}] {question}", flush=True)
        try:
            # Her senaryo kendi boş sohbet geçmişiyle bağımsız değerlendirilir.
            result = pipeline.ask(question, chat_history=[])
            print(f"Kanal: {result.get('type')} | Yanıt: {result.get('answer')}", flush=True)
            verify(result)
        except Exception as exc:
            failures.append(f"{name}: {type(exc).__name__}: {exc}")
            print(f"BAŞARISIZ ({perf_counter() - started:.2f} sn): {exc}", flush=True)
        else:
            print(f"BAŞARILI ({perf_counter() - started:.2f} sn)", flush=True)

    print(
        f"\nSonuç: {len(cases) - len(failures)}/{len(cases)} başarılı "
        f"({perf_counter() - total_start:.2f} sn).",
        flush=True,
    )
    if failures:
        raise AssertionError("Kabul testleri başarısız:\n" + "\n".join(failures))


if __name__ == "__main__":
    run_pipeline_test()
