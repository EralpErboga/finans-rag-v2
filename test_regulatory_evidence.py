import json
import unittest
from unittest.mock import Mock
from src.chains import RAGPipeline, ConversationBufferMemory
from src.regulatory_evidence import focused_provisions, complete_grounded_answer, unknown_letter_target


class RegulatoryEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.contexts = [{"source": "synthetic.txt", "section": "Madde X — Süre",
                          "text": "a) Motor Kontrol Üniteleri: 17 ay,\nb) Sensör Ağları: 9 ay."},
                         {"source": "groups.txt", "section": "Madde Y",
                          "text": "a) X Grubu: Üst sınır %31,\nb) Y Grubu: Üst sınır %42."}]

    def test_values_come_from_source_not_answer_table(self):
        result = focused_provisions("motor kontrol", self.contexts)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["value"], "17 ay")
        self.contexts[0]["text"] = "Motor Kontrol Üniteleri: 23 ay."
        self.assertEqual(focused_provisions("motor kontrol", self.contexts)[0]["value"], "23 ay")

    def test_different_property_does_not_force_numeric_row(self):
        self.assertEqual(focused_provisions("motor kontrol", self.contexts,
                         question="Motor kontrol bakım tarihi nedir?"), [])

    def test_multiple_letter_groups(self):
        result = focused_provisions("x ve y", self.contexts)
        self.assertEqual([r["value"] for r in result], ["Üst sınır %31", "Üst sınır %42"])
        self.assertEqual(focused_provisions("z grubu", self.contexts), [])
        self.assertTrue(unknown_letter_target("z grubu", self.contexts))
        self.assertTrue(unknown_letter_target("x ve z", self.contexts))
        self.assertFalse(unknown_letter_target("x ve y", self.contexts))

    def test_specific_match_beats_shared_word_and_multiple_targets_survive(self):
        self.contexts[0]["text"] = "a) Ölçüm Sistemleri: 19 yıl\nb) Kontrol Sistemleri: 6 yıl"
        self.assertEqual(len(focused_provisions("ölçüm sistemleri", self.contexts)), 1)
        self.assertEqual(len(focused_provisions("ölçüm sistemleri ve kontrol", self.contexts)), 2)

    def test_incomplete_wrong_unit_and_wrong_association_rejected(self):
        rows = focused_provisions("motor kontrol", self.contexts)
        for answer in ["Motor Kontrol Üniteleri", "Motor Kontrol Üniteleri 17 yıl.",
                       "Motor Kontrol Üniteleri 9 ay.", "Motor Kontrol Üniteleri 17 ay değildir."]:
            self.assertFalse(complete_grounded_answer(answer, rows), answer)
        self.assertTrue(complete_grounded_answer("Motor Kontrol Üniteleri: 17 ay.", rows))

    def test_swapped_group_values_rejected(self):
        rows = focused_provisions("x ve y", self.contexts)
        self.assertFalse(complete_grounded_answer(
            "X Grubu: Üst sınır %42. Y Grubu: Üst sınır %31.", rows))

    def test_fallback_is_short_and_only_cites_selected_article(self):
        pipeline = RAGPipeline.__new__(RAGPipeline)
        pipeline.llm_model = "test"
        pipeline.search_mevzuat = Mock(return_value=self.contexts)
        pipeline._chat = Mock(return_value={"message": {"content": json.dumps(
            {"answer": "Bilgi yok", "source_ids": [1]})}})
        result = pipeline.answer_mevzuat("motor kontrol için süre?", "motor kontrol")
        self.assertIn("17 ay", result["answer"])
        self.assertNotIn("%31", result["answer"])
        self.assertEqual([r["source"] for r in result["sources"]], ["synthetic.txt"])

    def test_followup_replaces_previous_subject(self):
        pipeline = RAGPipeline.__new__(RAGPipeline)
        pipeline.memory = ConversationBufferMemory()
        pipeline.memory.add_user_message("Motorlar için bakım aralığı kaç aydır?")
        pipeline.memory.messages.extend([
            {"role": "user", "content": "Hangi soruda bakım dedim?"},
            {"role": "assistant", "content": "Bir geçmiş yanıtı", "badge": "CHAT_META"}])
        rewritten = pipeline.rewrite_query("sensörler")
        self.assertEqual(rewritten, "sensörler için bakım aralığı kaç aydır?")

    def test_technical_question_does_not_take_hybrid_path(self):
        pipeline = RAGPipeline.__new__(RAGPipeline)
        pipeline.llm_model = "test"
        pipeline._chat = Mock(return_value={"message": {"content": '{"intent":"HYBRID"}'}})
        self.assertEqual(pipeline._classify_intent("Motor bakım aralığı kaç gündür?")["intent"], "MEVZUAT")
        self.assertEqual(pipeline._classify_intent("Mevzuat şartının gelir tablomuzdaki etkisi nedir?")["intent"], "HYBRID")


if __name__ == "__main__":
    unittest.main()
