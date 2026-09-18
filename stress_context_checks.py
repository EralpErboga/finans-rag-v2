"""Four bounded offline context probes; model fallback is reported, not guessed."""
import json
from unittest.mock import Mock
from src.chains import RAGPipeline, ConversationBufferMemory
from stress_test_20260916 import OUT, write, verify


def history(turns):
    result=[]
    for question,channel in turns:
        result.extend([{'role':'user','content':question},
                       {'role':'assistant','content':'Kontrollü test kaydı; gerçek model cevabı değildir.','badge':channel}])
    return result


def run():
    verify()
    base=[('Ölçüm sistemlerini kaç yıl üzerinden amorti ediyoruz?','MEVZUAT'),
          ('ölçüm sistemlerimiz','MEVZUAT')]
    cases=[
        ('C1',base+[('ölç sis','MEVZUAT')], 'Repeated abbreviation should still resolve to full topic.'),
        ('C2',base+[('ölçü sistematiği','MEVZUAT')], 'Two expansions: must not choose one automatically.'),
        ('C3',base+[('Yatırım raporumuzu hangi ay gönderiyoruz?','MEVZUAT')], 'Same-channel switch: must not silently attach reporting date to amortisation topic.'),
        ('C4',base+[('Sermaye hesabımızın güncel tutarı ne?','FINANCE')], 'Channel changed: do not force old regulatory topic.'),
    ]
    rows=[]
    for ident,turns,expected in cases:
        pipeline=RAGPipeline.__new__(RAGPipeline);pipeline.memory=ConversationBufferMemory()
        pipeline._sync_memory_from_history(history(turns))
        pipeline._classify_intent=Mock(return_value={'intent':'MODEL_FALLBACK_NOT_EVALUATED'})
        result=pipeline.route_and_resolve('ölç sis')
        rows.append(dict(id=ident,expected=expected,result=result,
                         model_fallback_calls=pipeline._classify_intent.call_count,
                         scope='Deterministic context handling only, synthetic channel-labelled history; no live answer claim.'))
    write('context_probes.json',rows)
    print(json.dumps(rows,ensure_ascii=False,indent=2))


if __name__=='__main__':run()
