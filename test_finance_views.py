"""Offline checks of ambiguous financial views using unrelated synthetic values."""
import unittest
from unittest.mock import Mock
import test_general_capabilities as capabilities
from src.chains import RAGPipeline, ConversationBufferMemory
from src.conversation import execute_history_plan


class FinanceViewsTests(unittest.TestCase):
    def test_single_word_followup_explains_missing_second_word(self):
        plan = {'actions': [dict(operation='word', question_index=1, question_origin='start',
                                 word_index=2, word_origin='end', terms=[])]}
        result = execute_history_plan(plan, [{'role': 'user', 'content': 'cihazlar'}])
        self.assertIn('toplam 1 kelime', result['answer'])
        self.assertIn('2. kelime yer almamaktadır', result['answer'])

    def setUp(self):
        helper = capabilities.GeneralCapabilitiesTests()
        self.addCleanup(helper.doCleanups)
        engine = helper.make_engine()
        with engine.repository.get_connection() as conn:
            conn.execute("UPDATE mizan SET hesap_adi='Örnek (Deneme Varlığı)' WHERE hesap_kodu='111'")
            conn.execute("UPDATE bilanco SET kalem='Deneme Varlığı (net)'")
        self.pipeline = RAGPipeline.__new__(RAGPipeline)
        self.pipeline.finance_engine = engine
        self.pipeline.memory = ConversationBufferMemory()
        self.pipeline._chat = Mock(side_effect=AssertionError('No model needed for paired views'))
        self.pipeline._finance_plan = Mock(side_effect=AssertionError('No model plan needed'))

    def test_both_views_with_sources_without_question_or_sum(self):
        result = self.pipeline.answer_finance('Deneme varlığımız ne kadar?')
        for expected in ['Mizan (brüt)', '100,00 TL', 'Bilanço (net)', '60,00 TL']:
            self.assertIn(expected, result['answer'])
        self.assertEqual(result['raw_data']['operation'], 'lookup')
        self.assertNotIn('calculation', result['raw_data'])
        self.assertEqual(len(result['sources']), 2)
        self.assertNotIn('Hangi tutarı', result['answer'])
        self.assertNotIn('?', result['answer'])

    def test_voluntary_selection_returns_only_selected_view(self):
        question = 'Deneme varlığımız ne kadar?'
        result = self.pipeline.answer_finance(question)
        for metadata in [True, False]:
            history = [{'role': 'user', 'content': question},
                       {'role': 'assistant', 'content': result['answer'], 'badge': 'FINANCE',
                        **({'finance_views': result['finance_views']} if metadata else {})}]
            for selection, amount, excluded in [('brüt', '100,00 TL', '60,00 TL'), ('net', '60,00 TL', '100,00 TL')]:
                with self.subTest(metadata=metadata, selection=selection):
                    answer = self.pipeline.ask(selection, history)
                    self.assertEqual(answer['type'], 'FINANCE')
                    self.assertIn(amount, answer['answer'])
                    self.assertNotIn(excluded, answer['answer'])
                    self.assertEqual(len(answer['sources']), 1)

    def test_explicit_scope_arithmetic_and_unrelated_questions_not_expanded(self):
        for question in ['111 hesabı', 'Deneme varlığının net tutarı', 'Deneme varlığının mizan tutarı',
                         'Deneme varlığı ile kaynak toplamı', 'Deneme varlığının oranı', 'Kasa ne kadar?']:
            with self.subTest(question=question):
                self.assertEqual(self.pipeline._ambiguous_finance_views(question), [])

    def test_multiple_matching_gross_accounts_are_not_guessed(self):
        with self.pipeline.finance_engine.repository.get_connection() as conn:
            conn.execute("UPDATE mizan SET hesap_adi='Deneme Varlığı' WHERE hesap_kodu='555'")
        self.assertEqual(self.pipeline._ambiguous_finance_views('Deneme varlığımız ne kadar?'), [])


if __name__ == '__main__':
    unittest.main()
