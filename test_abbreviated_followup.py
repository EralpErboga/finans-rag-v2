"""Offline routing and evidence checks; abbreviations come from session text."""
import unittest
from unittest.mock import Mock
from src.chains import RAGPipeline, ConversationBufferMemory


class AbbreviatedFollowupTests(unittest.TestCase):
    def setUp(self):
        self.pipeline = RAGPipeline.__new__(RAGPipeline)
        self.pipeline.memory = ConversationBufferMemory()
        self.history = []
        for question in ['Trafo merkezleri için amortisman süresi kaç yıldır?', 'bilgi işlem', 'sayaçlar']:
            self.history.extend([{'role': 'user', 'content': question},
                                 {'role': 'assistant', 'content': 'Kaynaklı yanıt', 'badge': 'MEVZUAT'}])
        self.pipeline._classify_intent = Mock(return_value={'intent': 'CHAT_META'})

    def test_unique_abbreviation_resolves_before_wrong_router_result(self):
        self.pipeline.answer_mevzuat = Mock(return_value={'type': 'MEVZUAT', 'answer': 'Kaynaklı yanıt'})
        result = self.pipeline.ask('bil iş', self.history)
        self.assertEqual(result['type'], 'MEVZUAT')
        self.pipeline._classify_intent.assert_not_called()
        self.pipeline.answer_mevzuat.assert_called_once_with(
            'bilgi işlem için amortisman süresi kaç yıldır?', original_question='bilgi işlem')

    def test_unrelated_abbreviation_is_derived_from_history(self):
        self.history[2]['content'] = 'ölçüm cihazları'
        self.pipeline._sync_memory_from_history(self.history)
        decision = self.pipeline.route_and_resolve('ölç cih')
        self.assertEqual(decision['target_query'], 'ölçüm cihazları')

    def test_explicit_history_search_keeps_its_route(self):
        self.pipeline._sync_memory_from_history(self.history)
        self.assertEqual(self.pipeline.route_and_resolve('hangi soruda iş dedim')['intent'], 'CHAT_META')
        self.pipeline._classify_intent.assert_called_once()

    def test_ambiguous_abbreviation_does_not_choose_a_topic(self):
        self.history.extend([{'role': 'user', 'content': 'bilim işleri'},
                             {'role': 'assistant', 'content': 'Yanıt', 'badge': 'MEVZUAT'}])
        self.pipeline._sync_memory_from_history(self.history)
        self.assertNotIn('target_query', self.pipeline.route_and_resolve('bil iş'))

    def test_other_channel_does_not_reuse_old_topic(self):
        self.history.extend([{'role': 'user', 'content': 'Kasa bakiyesi nedir?'},
                             {'role': 'assistant', 'content': 'Yanıt', 'badge': 'FINANCE'}])
        self.pipeline._sync_memory_from_history(self.history)
        self.assertNotIn('target_query', self.pipeline.route_and_resolve('bil iş'))


if __name__ == '__main__':
    unittest.main()
