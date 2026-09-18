"""Offline runtime regressions. No Ollama, Qdrant or project DB is used."""
import json
import unittest
from unittest.mock import patch

from httpx import ConnectError, ReadTimeout
from ollama import ResponseError

from src.chains import RAGPipeline
from src.config import settings
from qdrant_client.http.exceptions import ResponseHandlingException


def response(content):
    return {"message": {"content": content}}


class RuntimeErrorTests(unittest.TestCase):
    def setUp(self):
        self.start("httpx.Client.send", side_effect=AssertionError("Offline test attempted HTTP"))
        self.client_factory = self.start("src.chains.Client")
        self.start("src.chains.QdrantClient")
        engine_factory = self.start("src.chains.FinanceEngine")
        self.engine = engine_factory.return_value
        self.engine.get_finance_catalog.return_value = [
            {"id": "mizan:100", "source": "mizan", "key": "100", "label": "Kasa"}
        ]
        self.engine.execute_finance_plan.return_value = {
            "status": "success", "operation": "lookup",
            "data": [{"id": "mizan:100", "label": "Kasa", "value": 270000.0,
                      "source": "mizan", "source_label": "Kasa", "account_code": "100"}],
        }
        self.start("src.chains.logger")
        self.pipeline = RAGPipeline()
        self.client = self.client_factory.return_value

    def start(self, target, **kwargs):
        item = patch(target, **kwargs)
        value = item.start()
        self.addCleanup(item.stop)
        return value

    def assert_error(self, result, fragment):
        self.assertEqual(result["type"], "ERROR", result)
        self.assertIn(fragment, result["answer"])
        self.assertEqual(result["sources"], [])

    def test_missing_model(self):
        self.client.chat.side_effect = ResponseError("model not found", status_code=404)
        self.assert_error(self.pipeline.ask("Kasa ne kadar?"), "yerel model bulunamadı")

    def test_qdrant_error_identifies_data_service(self):
        result = self.pipeline._error_result(ResponseHandlingException(ReadTimeout("timed out")))
        self.assert_error(result, "Qdrant")

    def test_memory_failure(self):
        for message in ("CUDA out of memory", "failed to allocate CUDA0 buffer", "cudaMalloc failed"):
            with self.subTest(message=message):
                self.client.chat.side_effect = ResponseError(message, status_code=500)
                self.assert_error(self.pipeline.ask("Kasa ne kadar?"), "bellek yetersiz")

    def test_connection_and_timeout(self):
        for failure in (ConnectionError("stopped"), ConnectError("refused"), ReadTimeout("timeout")):
            with self.subTest(failure=type(failure).__name__):
                self.client.chat.side_effect = failure
                self.assert_error(self.pipeline.ask("Kasa ne kadar?"), "servisine ulaşılamadı")

    def test_invalid_router_json_and_class(self):
        for content in ("x", "[]", "null", "{}", '{"intent":"UNKNOWN"}'):
            with self.subTest(content=content):
                self.client.chat.side_effect = None
                self.client.chat.return_value = response(content)
                self.assert_error(self.pipeline.ask("Kasa ne kadar?"), "geçerli bir kategoriye ayıramadı")

    def test_out_of_scope(self):
        self.client.chat.return_value = response('{"intent":"OUT_OF_SCOPE"}')
        result = self.pipeline.ask("Yarın hava nasıl?")
        self.assertEqual(result["type"], "OUT_OF_SCOPE")
        self.assertFalse(result["sources"])
        self.engine.execute_finance_plan.assert_not_called()

    def test_supported_router_categories(self):
        for intent in ("FINANCE", "MEVZUAT", "HYBRID", "CHAT_META", "OUT_OF_SCOPE"):
            with self.subTest(intent=intent):
                self.client.chat.return_value = response(json.dumps({"intent": intent}))
                # Semantic normalization may downgrade HYBRID without financial intent.
                expected = "MEVZUAT" if intent == "HYBRID" else intent
                self.assertEqual(self.pipeline._classify_intent("test girdisi")["intent"], expected)

    def test_invalid_finance_plan_is_error_not_missing_data(self):
        self.client.chat.side_effect = [response('{"intent":"FINANCE"}'), response("not json")]
        result = self.pipeline.ask("Kasa ne kadar?")
        self.assert_error(result, "geçerli bir sorgu planına")
        self.engine.execute_finance_plan.assert_not_called()

    def test_unknown_catalog_item_is_rejected(self):
        self.client.chat.side_effect = [
            response('{"intent":"FINANCE"}'),
            response('{"operation":"lookup","items":["mizan:999"]}'),
        ]
        self.engine.execute_finance_plan.side_effect = ValueError("unknown")
        self.assert_error(self.pipeline.ask("Bilinmeyen bakiye?"), "güvenli biçimde eşleştirilemedi")

    def test_narration_failure_remains_runtime_error(self):
        self.client.chat.side_effect = [
            response('{"intent":"FINANCE"}'),
            response('{"operation":"lookup","items":["mizan:100"]}'),
            ReadTimeout("narration timeout"),
        ]
        self.assert_error(self.pipeline.ask("Kasa ne kadar?"), "servisine ulaşılamadı")

    def test_model_calls_use_configured_context(self):
        self.client.chat.return_value = response('{"intent":"OUT_OF_SCOPE"}')
        self.pipeline.ask("Yarın hava nasıl?")
        self.assertEqual(self.client.chat.call_args.kwargs["options"]["num_ctx"], settings.num_ctx)
        other = RAGPipeline(num_ctx=2048)
        other._chat(model=other.llm_model, messages=[], options={"num_predict": 1})
        self.assertEqual(self.client.chat.call_args.kwargs["options"]["num_ctx"], 2048)


if __name__ == "__main__":
    unittest.main(verbosity=2)
