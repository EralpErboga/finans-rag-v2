"""Synthetic regressions for context, arithmetic provenance and source fidelity."""
import json
import unittest
import subprocess
import sys
import textwrap
from unittest.mock import Mock, patch
from src.chains import RAGPipeline, ConversationBufferMemory
from src.intent_rules import route_contract, catalogue_pairs
from src.conversation import explicit_history_plan, execute_history_plan
from src.regulatory_evidence import condition_compatible


class AccuracyTests(unittest.TestCase):
    def pipeline(self):
        p = RAGPipeline.__new__(RAGPipeline)
        p.llm_model = 'test'
        p.memory = ConversationBufferMemory()
        return p

    def test_complete_commands_do_not_inherit_previous_question(self):
        p = self.pipeline()
        p.memory.add_user_message('Pompa için bakım süresi kaç gündür?')
        for question in ['Ödenmiş sermayeyi göster.', 'Bakımı değil, garanti süresini öğrenmek istiyorum.',
                         'İkinci çeyrek için son tarihi söyle.',
                         'Aynı hesabı iki kere yazdım: 741 ve 741 topla.',
                         'İkinci dönemin bildirimi için son ay hangisi?',
                         'Burada kontrol üniteleri derken hangi varlıklar kastediliyor?']:
            self.assertEqual(p.rewrite_query(question), question)

    def test_normative_questions_are_not_account_balances(self):
        for question in ['Donanımı kaç yıl amorti ederiz?', 'İkinci çeyrek verilerini ne zaman gönderiyoruz?',
                         'Kesin kapanış verilerinde de aynı ay mı geçerli?',
                         'Mizandaki borç ve alacak için neyi denetlemeliyim?']:
            self.assertEqual(route_contract(question, 'FINANCE'), 'MEVZUAT')
        self.assertEqual(route_contract('744 hesabındaki yatırım varlık tabanına uygun mu?', 'FINANCE'), 'HYBRID')
        self.assertEqual(route_contract('Amortisman giderinin tutarı nedir?', 'FINANCE'), 'FINANCE')

    def test_repeated_abbreviation_has_one_expansion(self):
        p = self.pipeline()
        for q in ['Cihazlar için bakım süresi kaç gün?', 'motor kontrol', 'mot kon']:
            p.memory.messages.extend([{'role': 'user', 'content': q},
                                      {'role': 'assistant', 'content': 'Yanıt', 'badge': 'MEVZUAT'}])
        p._classify_intent = Mock(side_effect=AssertionError('No model required'))
        self.assertEqual(p.route_and_resolve('mot kon')['target_query'], 'motor kontrol')

    def test_short_followups_do_not_grow_the_context_recursively(self):
        p = self.pipeline()
        p.memory.messages = [
            {'role': 'user', 'content': 'Kontrol ünitelerinin kapsamı nedir?'},
            {'role': 'assistant', 'badge': 'MEVZUAT', 'content': 'Kaynak'},
            {'role': 'user', 'content': 'motorlar'},
            {'role': 'assistant', 'badge': 'MEVZUAT', 'content': 'Kaynak', 'domain_context': {
                'query': 'motorlar. Şu temel soru kalıbındaki özellik soruluyor: Kontrol ünitelerinin kapsamı nedir?'}}]
        query = p.rewrite_query('sensörler')
        self.assertEqual(query.count('Şu temel soru'), 1)
        self.assertNotIn('motorlar', query)

    def test_reference_resolution_cannot_rewrite_the_requested_property(self):
        p = self.pipeline()
        p.memory.add_user_message('Kontrol üniteleri hangi varlıkları kapsıyor?')
        p._chat = Mock(return_value={'message': {'content': '{"referent":"Kontrol üniteleri"}'}})
        question = 'Aynı varlıkların garanti koşulları neler?'
        self.assertEqual(p._resolve_reference(question), question + ' İlgili konu/kalem: Kontrol üniteleri.')

    def test_abbreviation_after_property_switch_requests_clarification(self):
        p = self.pipeline()
        for q, channel in [('Motorlar için bakım aralığı kaç gün?', 'MEVZUAT'),
                           ('kontrol üniteleri', 'MEVZUAT'), ('Raporlama takvimi nedir?', 'MEVZUAT')]:
            p.memory.messages.extend([{'role': 'user', 'content': q},
                                      {'role': 'assistant', 'content': 'Yanıt', 'badge': channel}])
        self.assertEqual(p.route_and_resolve('kon ün')['intent'], 'CLARIFY')

    def test_abbreviation_after_channel_switch_does_not_invent_financial_match(self):
        p = self.pipeline()
        for q, channel in [('kontrol üniteleri', 'MEVZUAT'), ('Nakit bakiyesi ne kadar?', 'FINANCE')]:
            p.memory.messages.extend([{'role': 'user', 'content': q},
                                      {'role': 'assistant', 'content': 'Yanıt', 'badge': channel}])
        self.assertEqual(p.route_and_resolve('kon ün')['intent'], 'CLARIFY')

    def test_source_date_is_returned_verbatim(self):
        p = self.pipeline()
        context = {'source': 'synthetic', 'section': 'Bildirim',
                   'text': 'Başvuru dönemi: Ağustos ayı sonu.'}
        p._chat = Mock(return_value={'message': {'content': '{"passage_ids":[1]}'}})
        result = p._extractive_regulatory_answer('Son başvuru ayı?', [context])
        self.assertIn(context['text'], result['answer'])
        self.assertEqual(result['sources'], [context])
        context['text'] = 'Başvuru dönemi: Kasım ayı sonu.'
        self.assertIn('Kasım', p._extractive_regulatory_answer('Son başvuru ayı?', [context])['answer'])

    def test_invalid_evidence_ids_cannot_be_rendered(self):
        p = self.pipeline()
        p._chat = Mock(return_value={'message': {'content': '{"passage_ids":[99]}'}})
        result = p._extractive_regulatory_answer('Son tarih?', [
            {'source': 'test', 'section': 'Takvim', 'text': 'Başvuru: Haziran.'}])
        self.assertFalse(result['sources'])
        self.assertNotIn('Haziran', result['answer'])

    def test_different_reporting_condition_is_not_a_late_submission_penalty(self):
        self.assertFalse(condition_compatible('Bildirim gecikirse yaptırım nedir?',
                                             'Yanlış bildirim için yaptırım uygulanır.'))
        self.assertTrue(condition_compatible('Bildirim gecikirse yaptırım nedir?',
                                            'Bildirim gecikirse ek inceleme yapılır.'))

    def test_exhaustive_message_list_is_not_regulatory_reporting(self):
        question = 'Sohbetteki tüm mesajlarımı numaralandır.'
        plan = explicit_history_plan(question)
        result = execute_history_plan(plan, [{'role': 'user', 'content': 'Özgün içerik'}], request_text=question)
        self.assertEqual(result['answer'], 'Soru 1: Özgün içerik')

    def test_statutory_amount_alone_does_not_require_company_accounts(self):
        self.assertEqual(route_contract('Mevzuatta ceza kaç lira olarak belirtiliyor?', 'HYBRID'), 'MEVZUAT')

    def test_finance_followup_keeps_actual_ids(self):
        p = self.pipeline()
        p.finance_engine = Mock()
        p.finance_engine.execute_finance_plan.return_value = {
            'data': [{'id': 'mizan:741', 'label': 'Sentetik', 'value': 37,
                      'source': 'mizan', 'source_label': 'Sentetik'}]}
        history = [{'role': 'assistant', 'badge': 'FINANCE', 'domain_context':
                    {'query': 'Önceki soru', 'items': ['mizan:741', 'mizan:742']}}]
        p.ask('Bu iki kalemi toplama, ayrı göster.', history)
        p.finance_engine.execute_finance_plan.assert_called_once_with(
            {'operation': 'lookup', 'items': ['mizan:741', 'mizan:742']})

    def test_hybrid_reference_does_not_select_a_new_account(self):
        p = self.pipeline()
        p._referenced_items = ['mizan:741']
        p.search_mevzuat = Mock(return_value=[{'source': 'test', 'section': 'Madde X',
                                             'text': 'Madde X\n(1) Teknik ölçüm gereklidir.'}])
        p._finance_plan = Mock(side_effect=AssertionError('Must reuse the verified selection'))
        p.finance_engine = Mock()
        p.finance_engine.execute_finance_plan.return_value = {'operation': 'lookup', 'data': []}
        p.answer_hybrid('Bu tutardan teknik oran belirlenebilir mi?')
        p.finance_engine.execute_finance_plan.assert_called_once_with({'operation': 'lookup', 'items': ['mizan:741']})

    def test_pairs_come_from_catalogue_and_exclude_deductions(self):
        catalog = [{'id': 'mizan:741', 'source': 'mizan', 'label': 'Donanım (Kontrol Üniteleri)'},
                   {'id': 'mizan:742', 'source': 'mizan', 'label': 'Kontrol Üniteleri (-)'},
                   {'id': 'bilanco:19', 'source': 'bilanco', 'label': 'Kontrol Üniteleri (net)'}]
        self.assertEqual(catalogue_pairs(catalog), [('mizan:741', 'bilanco:19')])

    def test_selected_message_relative_reference(self):
        question = 'Az önce seçtiğin mesajdan bir öncekinin tamamını getir.'
        plan = explicit_history_plan(question)
        self.assertIsNotNone(plan)
        result = execute_history_plan(plan, [
            {'role': 'user', 'content': 'A'}, {'role': 'user', 'content': 'B'},
            {'role': 'assistant', 'history_result': {'indices': [2]}}], request_text=question)
        self.assertEqual(result['history_result']['indices'], [1])

    def test_finance_extra_number_or_wrong_label_rejected(self):
        p = self.pipeline()
        p.finance_engine = Mock()
        p._finance_plan = Mock(return_value={'operation': 'lookup', 'items': ['mizan:741']})
        p.finance_engine.execute_finance_plan.return_value = {'operation': 'lookup', 'data': [
            {'id': 'mizan:741', 'label': 'Donanım', 'value': 37, 'source': 'mizan', 'source_label': 'Donanım'}]}
        for answer in ['Sermaye 37,00 TL.', 'Donanım 37,00 TL. Cezanız 999 TL.']:
            p._chat = Mock(return_value={'message': {'content': answer}})
            result = p.answer_finance('Donanım tutarı?')
            self.assertEqual(result['answer'], 'Donanım: 37,00 TL.')

    def test_ui_retains_followup_metadata_without_rendering_it(self):
        # Isolate UI mocks and the Streamlit runtime from the other regression tests.
        code = textwrap.dedent('''
            from unittest.mock import Mock, patch
            from streamlit.testing.v1 import AppTest
            with patch('src.audit.record'), patch('src.access.require_access'):
                app = AppTest.from_file('app.py', default_timeout=20).run()
                context = {'query': 'Deneme', 'items': ['mizan:741']}
                app.session_state['pipeline'].ask = Mock(return_value={
                    'type': 'FINANCE', 'answer': 'Test yaniti.', 'sources': [], 'domain_context': context})
                app.chat_input[0].set_value('Deneme sorusu').run()
                assert not app.exception
                assert app.session_state['messages'][-1]['domain_context'] == context
                assert not any('mizan:741' in element.value for element in app.markdown)
        ''')
        process = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=45)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)


if __name__ == '__main__':
    unittest.main()
