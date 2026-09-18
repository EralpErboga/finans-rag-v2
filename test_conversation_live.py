"""Opt-in real Ollama acceptance checks; fixtures are never imported by production."""
import json
import time
import sys
from ollama import Client
from src.chains import RAGPipeline, ConversationBufferMemory
from src.config import settings


def main():
    pipeline = RAGPipeline.__new__(RAGPipeline)
    pipeline.memory = ConversationBufferMemory()
    pipeline.llm_model = settings.llm_model
    pipeline.model_options = {"temperature": 0, "num_ctx": settings.num_ctx, "num_predict": 600}
    pipeline.ollama_client = Client(host=settings.ollama_host, timeout=120)
    chat = pipeline._chat
    def traced_chat(**kwargs):
        response = chat(**kwargs)
        if isinstance(kwargs.get("format"), dict):
            print("PLAN: " + response["message"]["content"], flush=True)
        return response
    pipeline._chat = traced_chat
    history = []
    for question in [
        "Trafo merkezleri için amortisman süresi kaç yıldır?",
        "orta gerilim şebeke hatları", "bilgi işlem", "sayaçlar",
        "A grubu bölgelerde kayıp-kaçak hedef üst sınırı nedir?", "b ve c",
        "Kasa ve bankalardaki toplam nakit varlığımız nedir?",
        "253 nolu hesaptaki yatırımlarımızın DVT'ye giriş koşulları nelerdir?",
    ]:
        history.extend([{"role": "user", "content": question},
                        {"role": "assistant", "content": "Önceki yanıt", "badge": "MEVZUAT"}])
    cases = [
        ("1. soruda ne sordum", ["Soru 1: Trafo"]),
        ("ondan 2 sonrakinde ne sordum", ["Soru 3: bilgi işlem"]),
        ("1. sorudaki 3. kelime nedir", ["kelime: için"]),
        ("İlk sorumun sondan üçüncü kelimesi nedir?", ["sondan 3. kelime: süresi"]),
        ("hangi soruda dvt ve hangi soruda sayaç dedim", ["Soru 8: 253", "Soru 4: sayaçlar"]),
        ("hangi soruda dvt dedim? hangi soruda sayaç dedim?", ["Soru 8: 253", "Soru 4: sayaçlar"]),
        ("Geçmiş sorularımda banka ile ilgili ifadeyi ve bilgi ifadesini ayrı ayrı bul.",
         ["Soru 7: Kasa", "Soru 3: bilgi işlem"]),
        ("İkinci sorumun en son sözcüğünü getir.", ["kelime: hatları"]),
        ("neler konuştuk özetle", ["Soru 1: Trafo", "Soru 8: 253"]),
    ]
    if "--held-out" in sys.argv:
        cases = [
            ("Üçüncü mesajımın son sözcüğünü yaz.", ["Soru 3, sondan 1. kelime: işlem"]),
            ("Bundan bir önceki soruyu göster.", ["Soru 2: orta gerilim"]),
            ("Geçmişte gerilim ve nakit ifadelerinin geçtiği soruları ayrı ayrı getir.",
             ["Soru 2: orta gerilim", "Soru 7: Kasa"]),
        ]
    if "--reported" in sys.argv:
        cases = [
            ("neler konuştuk özetle", ["Soru 1: Trafo", "Soru 8: 253"]),
            ("1. soruda ne sordum", ["Soru 1: Trafo merkezleri için amortisman süresi kaç yıldır?"]),
            ("ondan 2 sonrakinde ne sordum", ["Soru 3: bilgi işlem"]),
            ("1. sorudaki 3. kelime nedir", ["Soru 1, 3. kelime: için"]),
            ("hangi soruda kasa dedim", ["Aranan ifade: kasa", "Soru 7: Kasa"]),
            ("hangi soruda kasa dedim", ["Aranan ifade: kasa", "Soru 7: Kasa"]),
            ("hangi soruda banka dedim", ["Aranan ifade: banka", "Soru 7: Kasa"]),
        ]
    failures = 0
    for question, expected in cases:
        start = time.monotonic()
        result = pipeline.ask(question, history)
        ok = (result["type"] == "CHAT_META" and all(text in result["answer"] for text in expected)
              and "Aranan ifade: ilgili" not in result["answer"]
              and ("Aranan ifade:" not in result["answer"] or
                   not any(f"Soru {n}:" in result["answer"] for n in range(9, 30))))
        failures += not ok
        print(json.dumps({"question": question, "passed": ok, "seconds": round(time.monotonic()-start, 1),
                          "result": result}, ensure_ascii=False), flush=True)
        history.extend([{"role": "user", "content": question},
                        {"role": "assistant", "content": result["answer"], "badge": result["type"],
                         **({"history_result": result["history_result"]} if "history_result" in result else {})}])
    print(f"RESULT: {len(cases)-failures}/{len(cases)}", flush=True)
    raise SystemExit(bool(failures))


if __name__ == "__main__":
    main()
