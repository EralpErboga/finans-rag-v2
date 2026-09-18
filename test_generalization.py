"""Paraphrase acceptance tests. Fixtures never enter application prompts or retrieval.

python test_generalization.py --model qwen2.5:7b-instruct-q4_K_M --report review_artifacts/generalization.json
Live history uses actual answers, not simulated assistant messages.
"""
import argparse
import json
from pathlib import Path
from time import perf_counter


def run(model=None, report=None):
    from src.chains import RAGPipeline
    pipeline = RAGPipeline(**({"llm_model": model} if model else {}))
    histories = {}
    # Expected values are independently checked against the dummy source files.
    cases = [
        ("life", "Ölçüm sistemlerinin faydalı ömrü kaç yıl kabul ediliyor?", "MEVZUAT", ("10",), None),
        ("life", "SCADA sistemleri için?", "MEVZUAT", ("5",), None),
        ("loss", "C grubunun kayıp-kaçak oranı için hedef tavan kaçtır?", "MEVZUAT", ("%18",), None),
        ("loss", "Peki B grubu?", "MEVZUAT", ("%12",), None),
        ("cash", "100 ile 102 hesap bakiyelerinin toplamını hesapla.", "FINANCE", ("24.700.000,00",), 24700000),
        ("capital", "Ödenmiş sermaye ile geçmiş yıllar kârlarını birlikte toplar mısın?", "FINANCE", ("68.200.000,00",), 68200000),
        ("expense", "Şirketin yönetim faaliyetlerine ait gider toplamı kaç TL?", "FINANCE", ("21.200.000,00",), 21200000),
        ("dvt", "255 hesabımızın bakiyesi kaç TL ve bu yatırımın düzenlenmiş varlık tabanına kabulü için hangi şartlar aranır?", "HYBRID", ("işletme", "program"), None),
        ("effect", "Kayıp-kaçak hedefi aşıldığında şirket gelirine etkisini mevcut kayıtlarla kesin hesaplayabilir miyiz?", "HYBRID", ("%2",), None),
    ]
    results = []
    for group, question, intent, terms, amount in cases:
        history = histories.setdefault(group, [])
        started = perf_counter()
        result = pipeline.ask(question, chat_history=history)
        errors = []
        if result.get("type") != intent:
            errors.append(f"intent: expected {intent}, got {result.get('type')}")
        for term in terms:
            if term.casefold() not in result.get("answer", "").casefold():
                errors.append(f"answer missing {term}")
        if amount is not None:
            values = [v for row in result.get("raw_data", {}).get("data", []) for v in row.values()]
            values.append(result.get("raw_data", {}).get("calculation", {}).get("value"))
            if not any(isinstance(v, (float, int)) and abs(v - amount) < .01 for v in values):
                errors.append(f"SQL result missing {amount}")
        if intent in {"MEVZUAT", "HYBRID"} and not result.get("sources"):
            errors.append("no retrieved sources")
        if group == "effect":
            raw = result.get("raw_data", {}).get("data", [])
            if not any(row.get("hesap_kodu") == "602" and row.get("tutar") == 24300000 for row in raw):
                errors.append("Missing actual related income account")
            if any("oran" in key for row in raw for key in row):
                errors.append("Invented a physical rate from financial records")
            if not any(term in result.get("answer", "").lower() for term in ("eksik", "yetersiz", "bilinme", "bulunma", "belirleneme", "hesaplanama")):
                errors.append("No clear data insufficiency statement")
        record = {"question": question, "seconds": round(perf_counter() - started, 2),
                  "passed": not errors, "errors": errors, "result": result}
        results.append(record)
        print(json.dumps(record, ensure_ascii=False), flush=True)
        history.extend([{"role": "user", "content": question},
                        {"role": "assistant", "content": result.get("answer", "")}])
        if report:
            Path(report).write_text(json.dumps({"model": pipeline.llm_model, "cases": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    passed = sum(r["passed"] for r in results)
    print(f"{passed}/{len(results)} passed", flush=True)
    return passed == len(results)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model")
    parser.add_argument("--report")
    args = parser.parse_args()
    raise SystemExit(0 if run(args.model, args.report) else 1)
