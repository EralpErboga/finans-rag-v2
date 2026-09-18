"""History execution and orchestration regressions; no external services."""
import json
import unittest
from unittest.mock import Mock
from src.chains import RAGPipeline, ConversationBufferMemory
from src.conversation import execute_history_plan, history_schema_for_request, position_constraints


def action(operation, **kwargs):
    return dict(operation=operation, question_index=kwargs.get("index", 0),
                question_origin=kwargs.get("origin", "start"), word_index=kwargs.get("word_index", 0),
                word_origin=kwargs.get("word_origin", "start"), terms=kwargs.get("terms", []))


class HistoryPlanTests(unittest.TestCase):
    def setUp(self):
        self.history = []
        for text in ["Motor bakımı hangi ay yapılacak?", "Ölçüm cihazı nerede?", "İzin süreci tamamlandı mı?"]:
            self.history.extend([{"role": "user", "content": text},
                                 {"role": "assistant", "content": "Yanıt", "badge": "MEVZUAT"}])

    def run_plan(self, *actions):
        return execute_history_plan({"actions": list(actions)}, self.history)

    def test_word_directions_are_distinct(self):
        self.assertIn("hangi", self.run_plan(action("word", index=1, word_index=3))["answer"])
        self.assertIn("ay", self.run_plan(action("word", index=1, word_index=2, word_origin="end"))["answer"])

    def test_two_searches_exclude_previous_meta(self):
        self.history += [{"role": "user", "content": "Motor ve İzin araması"},
                         {"role": "assistant", "content": "Eski arama", "badge": "CHAT_META"}]
        result = self.run_plan(action("search", terms=["motor", "İZİN"]))
        self.assertEqual(result["history_result"]["indices"], [1, 3])
        self.assertNotIn("Soru 4:", result["answer"])
        self.assertIn("Soru 1:", result["answer"])
        self.assertIn("Soru 3:", result["answer"])

    def test_compound_operations(self):
        result = self.run_plan(action("question", index=2), action("word", index=1, word_index=1))
        self.assertIn("Ölçüm cihazı", result["answer"])
        self.assertIn("kelime: Motor", result["answer"])

    def test_listing_and_positions_count_all_previous_user_turns(self):
        self.history = []
        for index in range(1, 21):
            self.history.extend([
                {'role': 'user', 'content': f'Mesaj kelime{index} son'},
                {'role': 'assistant', 'content': 'Yanıt',
                 'badge': 'CHAT_META' if index == 5 or index > 14 else 'FINANCE'}])
        listed = self.run_plan(action('list'))
        self.assertEqual(len(listed['answer'].splitlines()) - listed['answer'].splitlines().count(''), 20)
        self.assertIn('Soru 5:', listed['answer'])
        self.assertIn('Soru 20:', listed['answer'])
        self.assertIn('Soru 18, 2. kelime: kelime18', self.run_plan(
            action('word', index=3, origin='end', word_index=2))['answer'])
        # The listing request itself becomes the 21st historical user message.
        self.history.extend([{'role': 'user', 'content': 'Geçmiş soruları listele'},
                             {'role': 'assistant', 'content': listed['answer'], 'badge': 'CHAT_META',
                              'history_result': listed['history_result']}])
        self.assertIn('Soru 19, 2. kelime: kelime19', self.run_plan(
            action('word', index=3, origin='end', word_index=2))['answer'])
        self.assertIn('Soru 21: Geçmiş soruları listele', self.run_plan(action('question', index=21))['answer'])

    def test_topic_rewrite_still_ignores_history_requests(self):
        pipeline = RAGPipeline.__new__(RAGPipeline)
        pipeline.memory = ConversationBufferMemory()
        pipeline._sync_memory_from_history([
            {'role': 'user', 'content': 'Motor için bakım süresi kaç gün?'},
            {'role': 'assistant', 'content': 'Yanıt', 'badge': 'MEVZUAT'},
            {'role': 'user', 'content': 'Son sorumda ne sordum?'},
            {'role': 'assistant', 'content': 'Motor...', 'badge': 'CHAT_META'}])
        self.assertEqual(pipeline.rewrite_query('pompalar'), 'pompalar için bakım süresi kaç gün?')

    def test_relative_uses_metadata_not_answer_text(self):
        self.history += [{"role": "user", "content": "Bir referans seç"},
                         {"role": "assistant", "content": "999. sorunuz: sahte",
                          "history_result": {"indices": [1]}}]
        self.assertIn("Soru 3: İzin", self.run_plan(action("question", index=2, origin="relative"))["answer"])

    def test_missing_and_ambiguous_anchor(self):
        for indices in [[], [1, 2]]:
            self.history += [{"role": "assistant", "history_result": {"indices": indices}}]
            self.assertIn("referans", self.run_plan(action("question", origin="relative"))["answer"])

    def test_out_of_bounds_never_wrap(self):
        for index in [0, -1, 99]:
            self.assertIn("yer almamaktadır", self.run_plan(action("question", index=index))["answer"])
        self.assertIn("yer almamaktadır", self.run_plan(action("word", index=1, word_index=99))["answer"])

    def test_last_question_and_empty_history(self):
        self.assertIn("Soru 3", self.run_plan(action("question", index=1, origin="end"))["answer"])
        self.history = []
        self.assertIn("yer almamaktadır", self.run_plan(action("list"))["answer"])

    def test_full_validation(self):
        for invalid in [None, {}, {"actions": []}, {"actions": [action("delete")]},
                        {"actions": [action("question", index=True)]},
                        {"actions": [action("word", index=1, word_index=0)]},
                        {"actions": [action("question", index=1, terms=["deneme"])]},
                        {"actions": [action("search", terms=[])]}]:
            with self.subTest(plan=invalid), self.assertRaises(ValueError):
                execute_history_plan(invalid, self.history)

    def test_search_handles_turkish_keyboard_variants(self):
        self.assertEqual(self.run_plan(action("search", terms=["olcum"]))["history_result"]["indices"], [2])

    def test_numeric_provenance_rejects_invented_position(self):
        with self.assertRaises(ValueError):
            execute_history_plan({"actions": [action("word", index=6, word_index=2)]},
                                 self.history, request_text="6. sorunun 4. kelimesi")

    def test_invalid_model_plan_retries_then_asks_for_clarification(self):
        pipeline = RAGPipeline.__new__(RAGPipeline)
        pipeline.memory = ConversationBufferMemory()
        pipeline.llm_model = "test"
        pipeline._chat = Mock(return_value={"message": {"content": '{"actions":[]}'}})
        result = pipeline.answer_chat_meta("Bir geçmiş isteği")
        self.assertEqual(pipeline._chat.call_count, 2)
        self.assertIn("açıkça belirtin", result["answer"])
        self.assertEqual(result["history_result"]["indices"], [])

    def test_model_only_plans_and_sync_preserves_metadata(self):
        pipeline = RAGPipeline.__new__(RAGPipeline)
        pipeline.memory = ConversationBufferMemory()
        pipeline.llm_model = "test"
        pipeline._sync_memory_from_history(self.history)
        pipeline._chat = Mock(return_value={"message": {"content": json.dumps(
            {"actions": [action("word", index=1, word_index=2, word_origin="end")]})}})
        result = pipeline.answer_chat_meta("Birinci sorunun sondan ikinci kelimesi")
        self.assertIn("kelime: ay", result["answer"])
        self.assertNotIn("Motor bakımı", str(pipeline._chat.call_args))
        pipeline._sync_memory_from_history([{"role": "assistant", **result}])
        self.assertEqual(pipeline.memory.messages[0]["history_result"]["indices"], [1])
        pipeline._sync_memory_from_history([])
        self.assertEqual(pipeline.memory.messages, [])

    def test_request_schema_cannot_substitute_search_word(self):
        schema = history_schema_for_request("Hangi soruda depo dedim?")
        fields = schema["properties"]["actions"]["items"]["properties"]
        self.assertIn("depo", fields["terms"]["items"]["enum"])
        self.assertNotIn("devo", fields["terms"]["items"]["enum"])
        self.assertNotIn("word", fields["operation"]["enum"])
        self.assertIn("word", history_schema_for_request("İkinci sorunun son sözcüğü")[
            "properties"]["actions"]["items"]["properties"]["operation"]["enum"])

    def test_executor_rejects_mutated_term_and_unsolicited_word(self):
        with self.assertRaises(ValueError):
            execute_history_plan({"actions": [action("search", terms=["devo"])]}, self.history,
                                 request_text="Hangi soruda depo dedim?")
        with self.assertRaises(ValueError):
            execute_history_plan({"actions": [action("word", index=1, word_index=1)]}, self.history,
                                 request_text="Birinci mesajımı göster")

    def test_absolute_reference_and_relative_direction_constraints(self):
        fields = history_schema_for_request("Dördüncü mesajın son kelimesi")[
            "properties"]["actions"]["items"]["properties"]
        self.assertNotIn("relative", fields["question_origin"]["enum"])
        with self.assertRaises(ValueError):
            execute_history_plan({"actions": [action("question", index=2, origin="relative")]},
                                 self.history, request_text="Seçilenden iki önceki soruyu göster")

    def test_explicit_relative_distance_and_numbered_question_origin(self):
        for request, expected in [("Seçilenden dört önceki mesajı getir.", ('relative', -4)),
                                  ("Ondan 7 sonrakinde ne sordum?", ('relative', 7)),
                                  ("İkinci mesajın son sözcüğünü yaz", ('start', None))]:
            self.assertEqual(position_constraints(request), expected)
            fields = history_schema_for_request(request)['properties']['actions']['items']['properties']
            self.assertEqual(fields['question_origin']['enum'], [expected[0]])
        self.assertEqual(position_constraints("İkinci soru ve üçüncü mesajı göster"), (None, None))
        self.assertEqual(position_constraints("Bundan önceki yılın giderini göster"), (None, None))
        for invalid in [action('question', index=0, origin='relative'),
                        action('question', index=-2, origin='relative')]:
            with self.assertRaises(ValueError):
                execute_history_plan({'actions': [invalid]}, self.history,
                                     request_text='Seçilenden dört önceki mesajı getir.')


if __name__ == "__main__":
    unittest.main(verbosity=2)
