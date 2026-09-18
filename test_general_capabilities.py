"""Offline invariants for deterministic finance, retrieval and history."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from src.chains import RAGPipeline
from src.conversation import execute_history_plan
from src.finance_engine import FinanceEngine, FinancialRepository
from src.retrieval import rerank


class GeneralCapabilitiesTests(unittest.TestCase):
    def test_absent_explicit_account_never_substituted_or_partially_summed(self):
        pipeline = RAGPipeline.__new__(RAGPipeline)
        pipeline.finance_engine = Mock()
        pipeline.finance_engine.get_finance_catalog.return_value = [
            dict(id='mizan:111', source='mizan', label='Deneme Varlığı')]
        pipeline._chat = Mock(side_effect=AssertionError('Must not ask model to replace a code'))
        for question in ['998 hesabı ne kadar?', '111 ile 998 hesaplarını topla']:
            self.assertEqual(pipeline._finance_plan(question), {'operation': 'lookup', 'items': []})

    def test_gross_net_plan_cannot_use_a_deduction_as_gross(self):
        from src.chains import PipelineError
        catalog = {'mizan:119': dict(source='mizan', label='Değer Düşüklüğü (-)')}
        with self.assertRaises(PipelineError):
            RAGPipeline._sanitize_finance_plan('Brüt ve net değeri karşılaştır',
                                               dict(operation='compare', items=['mizan:119']), catalog)

    def make_engine(self):
        temporary = tempfile.TemporaryDirectory(prefix="finance-plan-", ignore_cleanup_errors=True)
        self.addCleanup(temporary.cleanup)
        engine = FinanceEngine.__new__(FinanceEngine)
        engine.repository = FinancialRepository(str(Path(temporary.name) / "test.db"))
        with engine.repository.get_connection() as conn:
            conn.executemany(
                "INSERT INTO mizan(hesap_kodu,hesap_adi,borc_bakiye,alacak_bakiye) VALUES(?,?,?,?)",
                [("111", "Deneme Varlığı", 100.0, 0.0), ("555", "Deneme Kaynağı", 0.0, 40.0)],
            )
            conn.execute("INSERT INTO bilanco(tur,kalem,tutar) VALUES('AKTIF','Net Deneme',60)")
            conn.execute("INSERT INTO gelir_tablosu(kalem,tutar) VALUES('Deneme Gideri (-)',-25)")
        return engine

    def test_declarative_plan_calculates_in_code(self):
        engine = self.make_engine()
        total = engine.execute_finance_plan(
            {"operation": "sum", "items": ["mizan:111", "mizan:555"]})
        self.assertEqual(total["calculation"]["value"], 140.0)
        ratio = engine.execute_finance_plan(
            {"operation": "ratio", "items": ["bilanco:1", "gelir_tablosu:1"]})
        self.assertEqual(ratio["calculation"]["value"], 2.4)

    def test_plan_rejects_unknown_id_and_operation(self):
        engine = self.make_engine()
        for plan in ({"operation": "delete", "items": ["mizan:111"]},
                     {"operation": "lookup", "items": ["mizan:999"]}):
            with self.subTest(plan=plan), self.assertRaises(ValueError):
                engine.execute_finance_plan(plan)

    def test_explicit_codes_form_plan_without_model(self):
        pipeline = RAGPipeline.__new__(RAGPipeline)
        pipeline.llm_model = "test-model"
        pipeline.finance_engine = Mock()
        pipeline.finance_engine.get_finance_catalog.return_value = [
            {"id": "mizan:111"}, {"id": "mizan:555"}]
        pipeline._chat = Mock(side_effect=AssertionError("Explicit codes need no model plan"))
        self.assertEqual(
            pipeline._finance_plan("111 ve 555 hesaplarını topla"),
            {"operation": "sum", "items": ["mizan:111", "mizan:555"]},
        )

    def test_finance_answer_is_narrated_and_has_human_sources(self):
        pipeline = RAGPipeline.__new__(RAGPipeline)
        pipeline.llm_model = "test-model"
        pipeline.finance_engine = Mock()
        pipeline._finance_plan = Mock(return_value={"operation": "lookup", "items": ["mizan:111"]})
        pipeline.finance_engine.execute_finance_plan.return_value = {
            "status": "success", "operation": "lookup",
            "data": [{"label": "Deneme Varlığı", "value": 100.0, "source": "mizan",
                      "source_label": "Deneme Varlığı", "account_code": "111"}],
        }
        pipeline._chat = Mock(return_value={"message": {"content": "Deneme Varlığı 100,00 TL tutarındadır."}})
        result = pipeline.answer_finance("Deneme varlığı ne kadar?")
        self.assertEqual(result["answer"], "Deneme Varlığı 100,00 TL tutarındadır.")
        self.assertEqual(result["sources"][0]["source"], "Mizan")
        self.assertIn("Hesap 111", result["sources"][0]["section"])

    def test_hybrid_rejects_invented_number_with_grounded_fallback(self):
        pipeline = RAGPipeline.__new__(RAGPipeline)
        pipeline.llm_model = "test-model"
        pipeline.search_mevzuat = Mock(return_value=[
            {"source": "dummy.txt", "section": "Madde X", "text": "Üst sınır %7'dir."}])
        pipeline._finance_plan = Mock(return_value={"operation": "lookup", "items": ["mizan:111"]})
        pipeline.finance_engine = Mock()
        pipeline.finance_engine.execute_finance_plan.return_value = {
            "status": "success", "operation": "lookup",
            "data": [{"label": "Deneme", "value": 100.0, "source": "mizan",
                      "source_label": "Deneme", "account_code": "111"}],
        }
        pipeline._chat = Mock(return_value={"message": {"content": "Ceza 999 TL'dir."}})
        result = pipeline.answer_hybrid("111 nolu hesabın etkisi nedir?")
        self.assertNotIn("999", result["answer"])
        self.assertIn("hesaplanamaz", result["answer"])
        self.assertEqual({s["source"] for s in result["sources"]}, {"dummy.txt", "Mizan"})

    def test_non_select_sql_is_rejected_and_null_is_json_null(self):
        engine = FinanceEngine.__new__(FinanceEngine)
        engine.repository = Mock()
        conn = sqlite3.connect(":memory:")
        self.addCleanup(conn.close)
        engine.repository.get_connection.return_value = conn
        self.assertEqual(engine.execute_sql("SELECT NULL AS x")["data"], [{"x": None}])
        self.assertEqual(engine.execute_sql("PRAGMA user_version = 12")["status"], "error")

    def test_retrieval_reranking(self):
        candidates = [{"text": "Sözleşmenin yürürlüğü", "score": .8},
                      {"text": "Motor sistemleri için faydalı ömür 12 yıldır", "score": .55}]
        self.assertIn("Motor", rerank("Motor sistemlerinin ömrü?", candidates, 1)[0]["text"])

    def test_history_operations_use_actual_messages(self):
        history = [{"role": "user", "content": s} for s in
                   ("İlk özgün soru burada", "İkinci örnek", "Üçüncü örnek")]
        action = {"operation": "word", "question_index": 1, "question_origin": "start",
                  "word_index": 4, "word_origin": "start", "terms": []}
        self.assertEqual(execute_history_plan({"actions": [action]}, history)["answer"],
                         "Soru 1, 4. kelime: burada")
        action.update(operation="list")
        self.assertIn("Soru 3: Üçüncü örnek",
                      execute_history_plan({"actions": [action]}, history)["answer"])

    def test_ui_does_not_render_sql_or_code(self):
        source = Path("app.py").read_text(encoding="utf-8")
        self.assertNotIn("st.code", source)
        self.assertNotIn("render_financial_data", source)
        self.assertNotIn("raw_data", source)

    def test_pipeline_has_no_text_to_sql_chain(self):
        source = Path("src/chains.py").read_text(encoding="utf-8")
        for forbidden in ("sql_chain", "PromptTemplate", "ChatOllama", "DİNAMİK SQL"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
