"""Opt-in live acceptance; no production module imports these questions."""
from src.chains import RAGPipeline


def main():
    pipeline = RAGPipeline()
    history = []
    cases = [
        ("Trafo merkezleri için amortisman süresi kaç yıldır?", ["20 yıl"], ["25 yıl"]),
        ("orta gerilim şebeke hatları", ["25 yıl"], ["20 yıl"]),
        ("bilgi işlem", ["5 yıl"], ["20 yıl", "25 yıl"]),
        ("sayaçlar", ["10 yıl"], ["20 yıl", "25 yıl"]),
        ("A grubu bölgelerde kayıp-kaçak hedef üst sınırı nedir?", ["%8"], ["%12", "%18"]),
        ("b ve c", ["%12", "%18"], ["%8"]),
        ("Ölçüm sistemlerinin faydalı ömrü ne kadar?", ["10 yıl"], ["20 yıl", "5 yıl"]),
        ("SCADA için faydalı ömür kaç yıl?", ["5 yıl"], ["25 yıl"]),
        ("C ve A gruplarının kayıp-kaçak üst hedefleri nedir?", ["%18", "%8"], ["%12"]),
    ]
    failed = 0
    for question, required, forbidden in cases:
        result = pipeline.ask(question, history)
        ok = (result["type"] == "MEVZUAT" and bool(result["sources"]) and
              all(text in result["answer"] for text in required) and
              not any(text in result["answer"] for text in forbidden))
        print(f"{'PASS' if ok else 'FAIL'} {question}\n{result['answer']}\n"
              f"Kaynak: {[c['section'] for c in result['sources']]}", flush=True)
        failed += not ok
        history.extend([{"role": "user", "content": question},
                        {"role": "assistant", "content": result["answer"], "badge": result["type"]}])
    negatives = [
        "D grubu bölgelerde kayıp-kaçak hedef üst sınırı nedir?",
        "Trafo merkezleri için bakım aralığı kaç gündür?",
    ]
    for question in negatives:
        result = pipeline.ask(question, [])
        ok = (result["type"] == "MEVZUAT" and not any(c.isdigit() for c in result["answer"])
              and any(word in result["answer"].lower() for word in ["bulunma", "belirtilme", "bilgi yok"]))
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'} {question}\n{result['answer']}", flush=True)
    total = len(cases) + len(negatives)
    print(f"RESULT: {total-failed}/{total}", flush=True)
    raise SystemExit(bool(failed))


if __name__ == "__main__":
    main()
