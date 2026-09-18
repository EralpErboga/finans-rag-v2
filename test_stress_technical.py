"""Six offline infrastructure/behaviour scenarios; no production edits."""
import unittest
from unittest.mock import Mock, patch
from httpx import ConnectError, ReadTimeout
from ollama import ResponseError
from qdrant_client.http.exceptions import ResponseHandlingException
from src.chains import RAGPipeline, ConversationBufferMemory


class StressTechnicalTests(unittest.TestCase):
    def pipeline(self):
        p=RAGPipeline.__new__(RAGPipeline)
        p.memory=ConversationBufferMemory();p.llm_model='mock'
        p._chat=Mock();return p

    def assert_failure(self, error, text):
        p=self.pipeline();p._chat.side_effect=error
        with patch('src.chains.logger'):
            result=p.ask('Müşteri alacak dökümünü inceleyebilir miyiz?',[])
        self.assertEqual(result['type'],'ERROR');self.assertIn(text,result['answer'])

    def test_01_ollama_unavailable(self):
        self.assert_failure(ConnectError('offline'),'servisine ulaşılamadı')

    def test_02_qdrant_unavailable(self):
        p=self.pipeline();p.route_and_resolve=Mock(return_value={'intent':'MEVZUAT','effective_query':'test'})
        p.search_mevzuat=Mock(side_effect=ResponseHandlingException(ConnectError('offline')))
        with patch('src.chains.logger'): result=p.ask('Gönderim takvimini açıkla',[])
        self.assertEqual(result['type'],'ERROR');self.assertIn('Qdrant',result['answer'])

    def test_03_model_missing(self):
        self.assert_failure(ResponseError('not found',status_code=404),'model bulunamadı')

    def test_04_timeout(self):
        self.assert_failure(ReadTimeout('timeout'),'zaman aşımına')

    def test_05_invalid_plan(self):
        for content in ['{broken', '{"operation":"lookup","items":["mizan:887"]}']:
            p=self.pipeline();p.route_and_resolve=Mock(return_value={'intent':'FINANCE','effective_query':'Müşteri dökümü'})
            p.finance_engine=Mock();p.finance_engine.get_finance_catalog.return_value=[
                {'id':'mizan:111','source':'mizan','label':'Deneme varlığı'}]
            p._chat.return_value={'message':{'content':content}}
            with patch('src.chains.logger'): result=p.ask('Müşteri dökümü',[])
            self.assertEqual(result['type'],'ERROR')

    @patch('src.access.require_access')
    def test_06_streamlit_preserve_and_clear(self, _access_gate):
        from streamlit.testing.v1 import AppTest
        app=AppTest.from_file('app.py',default_timeout=20).run()
        self.assertFalse(app.exception)
        messages=[{'role':'user','content':'Oturum kontrol girdisi'},
                  {'role':'assistant','content':'Kontrol yanıtı','badge':'FINANCE','sources':[]}]
        app.session_state['messages']=messages
        app.run();self.assertEqual(app.session_state['messages'],messages)
        button=next(b for b in app.button if b.label=='Sohbet Geçmişini Sıfırla')
        button.click().run()
        self.assertFalse(app.exception);self.assertEqual(app.session_state['messages'],[])


if __name__=='__main__': unittest.main()
