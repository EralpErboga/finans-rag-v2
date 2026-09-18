"""Canlı, sıralı niyet/bağlam kabul testi: python test_router.py.

Asistan geçmişi kontrollü bir test girdisidir; gerçek cevap üretimi
test_pipeline.py içinde ayrıca sınanır. Değerler 2024 dummy kaynaklarından gelir.
"""

from time import perf_counter


CONVERSATION_FLOW = [
    {
        "user": "A grubu bölgelerde kayıp-kaçak hedef üst sınırı nedir?",
        "simulated_assistant": (
            "Kurgusal Kayıp-Kaçak Tebliği Madde 3'e göre A grubu bölgelerde "
            "kayıp-kaçak hedef üst sınırı %8 olarak belirlenmiştir."
        ),
        "expected_intent": "MEVZUAT",
    },
    {
        "user": "bu sınır gelir tablomuzu nasıl etkiler?",
        "simulated_assistant": (
            "Kurgusal Tebliğ Madde 3'e göre hedef oranın üzerinde gerçekleşen "
            "kayıp-kaçak tutarı, ilgili yıl için şirketin düzenlenmiş gelir "
            "tavanından %2'ye kadar indirilebilir. Şirketimizin gerçekleşen "
            "kayıp-kaçak oranı verilmediği için parasal etki hesaplanamaz."
        ),
        "expected_intent": "HYBRID",
        "resolved_terms": ("a grubu", "kayıp"),
    },
    {
        "user": "peki ticari alacaklarımız ne kadar?",
        "simulated_assistant": (
            "2024 dummy bilançosunda net ticari alacaklar 20.400.000,00 TL'dir."
        ),
        "expected_intent": "FINANCE",
    },
    {
        "user": "ilk sorumda sana ne sormuştum?",
        "simulated_assistant": (
            "İlk sorunuz: 'A grubu bölgelerde kayıp-kaçak hedef üst sınırı nedir?' idi."
        ),
        "expected_intent": "CHAT_META",
    },
    {
        "user": "Yarın Samsun'da hava durumu nasıl olacak?",
        "simulated_assistant": (
            "Sadece EPDK mevzuatı ve finansal veriler konusunda yardımcı olabilirim."
        ),
        "expected_intent": "OUT_OF_SCOPE",
    },
]


def check_decision(decision, step):
    assert decision.get("intent") == step["expected_intent"], (
        f"Beklenen niyet {step['expected_intent']}, karar: {decision}"
    )
    effective_query = decision.get("effective_query", "")
    assert isinstance(effective_query, str) and effective_query.strip(), (
        f"Bağımsız soru boş veya geçersiz: {decision}"
    )
    for term in step.get("resolved_terms", ()):
        assert term in effective_query.casefold(), (
            f"'Bu sınır' atfında '{term}' bağlamı çözülmedi: {effective_query}"
        )


def run_real_dialogue_test():
    from src.chains import RAGPipeline

    print("Canlı, çok turlu router kabul testi başlatılıyor...", flush=True)
    pipeline = RAGPipeline()
    pipeline.memory.clear()
    print(f"Model: {pipeline.llm_model}", flush=True)
    failures = []
    total_start = perf_counter()
    for index, step in enumerate(CONVERSATION_FLOW, 1):
        started = perf_counter()
        print(f"\n[{index}. TUR] {step['user']}", flush=True)
        try:
            decision = pipeline.route_and_resolve(step["user"])
            print(f"Karar: {decision}", flush=True)
            check_decision(decision, step)
        except Exception as exc:
            failures.append(f"{index}. tur: {type(exc).__name__}: {exc}")
            print(f"BAŞARISIZ ({perf_counter() - started:.2f} sn): {exc}", flush=True)
        else:
            print(f"BAŞARILI ({perf_counter() - started:.2f} sn)", flush=True)

        # Sabit, kaynağı doğrulanmış geçmiş sonraki turu önceki hatadan bağımsız tutar.
        pipeline.memory.chat_memory.add_user_message(step["user"])
        pipeline.memory.chat_memory.add_ai_message(step["simulated_assistant"])

    print(
        f"\nSonuç: {len(CONVERSATION_FLOW) - len(failures)}/{len(CONVERSATION_FLOW)} başarılı "
        f"({perf_counter() - total_start:.2f} sn).",
        flush=True,
    )
    if failures:
        raise AssertionError("Router testleri başarısız:\n" + "\n".join(failures))


if __name__ == "__main__":
    run_real_dialogue_test()
