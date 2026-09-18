"""Two independently bounded live paraphrase probes; preserve original responses."""
import json
import logging
import time
from src.chains import RAGPipeline
from stress_test_20260916 import OUT, verify, write


def main():
    verify()
    if (OUT/'paraphrases.json').exists(): raise RuntimeError('Already run')
    results=json.loads((OUT/'results.json').read_text(encoding='utf-8'))
    if len(results)+2>36:raise RuntimeError('Query cap')
    history=[message for row in results if row['id']<=6 for message in row['messages']]
    cases=[('C5','Kasa bakiyesinin Bankalar bakiyesine yüzdesel oranını hesaplar mısın?',history,
            'Same financial target as Q7: 270000/24430000, approx %1.11, correct raw rows and sources.'),
           ('C6','Ölçüm sistemleri için mevzuatta belirlenen amortisman süresi nedir?',[],
            'Same regulatory target as Q1: 10 yıl, yönetmelik Madde 2; compare with Q1 incorrect result.')]
    output=[]
    logging.getLogger('httpx').setLevel(logging.WARNING)
    for ident,question,messages,expected in cases:
        pipeline=RAGPipeline();start=time.perf_counter();result=pipeline.ask(question,messages)
        row=dict(id=ident,question=question,expected=expected,result=result,seconds=round(time.perf_counter()-start,3))
        output.append(row);write('paraphrases.json',output)
        print(json.dumps(row,ensure_ascii=False),flush=True)
    verify()


if __name__=='__main__': main()
