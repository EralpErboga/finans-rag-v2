"""Targeted, opt-in real services test; questions are evaluation-only."""
from src.chains import RAGPipeline


def main():
    pipeline = RAGPipeline()
    cases = [
        ("253 nolu hesaptaki yatırımlarımızın DVT'ye giriş koşulları nelerdir?",
         ["205.500.000,00 TL", "işletmeye", "program", "253/255"], ["250.000,00 TL"]),
        ("Kayıp-kaçak geliri hedefin üzerinde mi ve bu bizim gelir tablomuzu nasıl etkiler?",
         ["24.300.000,00 TL", "%2"], ["24.550.000,00 TL", "250.000,00 TL"]),
    ]
    failed = 0
    for question, required, forbidden in cases:
        result = pipeline.ask(question, [])
        answer = result["answer"]
        passed = (result["type"] == "HYBRID" and all(s in answer for s in required)
                  and not any(s in answer for s in forbidden) and answer.rstrip().endswith(".")
                  and len(answer.split()) < 300 and bool(result["sources"])
                  and result.get("raw_data", {}).get("status") == "success")
        print(f"{'PASS' if passed else 'FAIL'} {question}\n{answer}\n"
              f"WORDS: {len(answer.split())}; SOURCES: {[s['section'] for s in result['sources']]}", flush=True)
        failed += not passed
    print(f"RESULT: {len(cases)-failed}/{len(cases)}", flush=True)
    raise SystemExit(bool(failed))


if __name__ == "__main__":
    main()
