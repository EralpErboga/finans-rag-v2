import unittest
from src.hybrid_evidence import restrict_context_plan, compact_contexts, valid_comment


class HybridEvidenceTests(unittest.TestCase):
    def test_explanatory_conjunction_does_not_sum_unrelated_income(self):
        catalog = [
            {"id": "gelir_tablosu:1", "source": "gelir_tablosu", "label": "Bakım Hizmeti Gelirleri"},
            {"id": "gelir_tablosu:2", "source": "gelir_tablosu", "label": "Diğer Gelirler"}]
        result = restrict_context_plan("Bakım hizmeti geliri hedefi aştı mı ve gelir tablomuzu nasıl etkiler?",
                                       {"operation": "sum", "items": [r["id"] for r in catalog]}, catalog)
        self.assertEqual(result, {"operation": "lookup", "items": ["gelir_tablosu:1"]})

    def test_explicit_arithmetic_preserved(self):
        plan = {"operation": "sum", "items": ["mizan:111", "mizan:112"]}
        self.assertEqual(restrict_context_plan("111 ve 112 topla", plan, []), plan)
        ratio = {"operation": "ratio", "items": ["mizan:111", "mizan:112"]}
        self.assertEqual(restrict_context_plan("varlıkların kaynaklara oranı ve mevzuat etkisi", ratio, []), ratio)

    def test_unknown_selection_rejected(self):
        with self.assertRaises(ValueError):
            restrict_context_plan("Gelir etkisi", {"operation": "lookup", "items": ["unknown"]}, [])

    def test_excerpt_never_cuts_paragraph(self):
        context = {"section": "Madde X", "text": "Madde X\n(1) Kısa hüküm.\n(2) Bu ikinci paragraf bütçeye sığmayacak."}
        excerpts, sources = compact_contexts([context], word_budget=4)
        self.assertEqual(excerpts, ["Madde X\n\n(1) Kısa hüküm."])
        self.assertEqual(sources, [context])
        introduction = {"section": "Giriş", "text": "Giriş\nUzun belge tanıtımı."}
        self.assertEqual(compact_contexts([context, introduction])[1], [context])

    def test_truncated_and_unverified_comment_rejected(self):
        for text, response in [
            ("Belgeler doğrulanmadan kesin karar verile", {}),
            ("Eksik belge var. Ceza 90 TL.", {}),
            ("Belgeler doğrulanmalıdır.", {"done_reason": "length"})]:
            self.assertFalse(valid_comment(text, response))
        self.assertTrue(valid_comment("Eksik teknik ölçümler doğrulanmadan parasal etki hesaplanamaz.", {}))


if __name__ == "__main__":
    unittest.main()
