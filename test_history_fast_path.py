import unittest
from unittest.mock import Mock
from src.chains import RAGPipeline, ConversationBufferMemory
from src.conversation import explicit_history_plan, history_schema_for_request, execute_history_plan, history_term_matches


class HistoryFastPathTests(unittest.TestCase):
    def test_exact_positions_need_no_model_calls(self):
        pipeline = RAGPipeline.__new__(RAGPipeline)
        pipeline.memory = ConversationBufferMemory()
        pipeline._chat = Mock(side_effect=AssertionError('Unexpected model call'))
        history = [{'role': 'user', 'content': f'Kayıt sıra{i} bitti'} for i in range(1, 8)]
        for question, expected in [('3. sorudaki sondan 2. kelime', 'sıra3'),
                                   ('sondan 3. sorunun baştan 2. kelimesi ne', 'sıra5'),
                                   ('2. soruda ne sordum', 'Kayıt sıra2 bitti'),
                                   ('neler konuştuk özetle', 'Soru 7:')]:
            result = pipeline.ask(question, history)
            self.assertEqual(result['type'], 'CHAT_META')
            self.assertIn(expected, result['answer'])
        pipeline._chat.assert_not_called()

    def test_positions_are_locked_independently(self):
        question = '3. sorudaki sondan 2. kelime'
        fields = history_schema_for_request(question)['properties']['actions']['items']['properties']
        self.assertEqual(fields['question_index']['enum'], [3])
        self.assertEqual(fields['word_index']['enum'], [2])
        for wrong in [2, 11]:
            plan = explicit_history_plan(question)
            plan['actions'][0]['question_index'] = wrong
            with self.assertRaises(ValueError):
                execute_history_plan(plan, [], request_text=question)

    def test_domain_and_compound_questions_are_not_captured(self):
        for question in ['253 hesabının mevzuata göre durumu nedir?', 'Soru bankası gideri ne kadar?',
                         '3. soruyu getir ve 5. soruyu göster', 'Bundan iki önceki soruyu göster']:
            self.assertIsNone(explicit_history_plan(question))

    def test_search_matches_prefixes_not_middle_of_words(self):
        for term, text in [('iş', 'bilgi işlem'), ('banka', 'Bankalardaki bakiye'),
                           ('sayaç', 'sayaçlar'), ('bilgi işlem', 'Bilgi işlemde sorun')]:
            self.assertTrue(history_term_matches(term, text))
        for text in ['amortisman', 'Trafo için ömür', 'geçmiş']:
            self.assertFalse(history_term_matches('iş', text))


if __name__ == '__main__':
    unittest.main()
