"""Offline source parity and index dimension checks for the local dummy release."""
import sqlite3
import unittest
from unittest.mock import Mock

import pandas as pd
from src.config import settings
from src.finance_engine import ExcelImporter
from src.ingest_qdrant import QdrantIngestor


class ReleaseIntegrityTests(unittest.TestCase):
    def test_database_matches_dummy_workbook(self):
        with pd.ExcelFile(settings.excel_path) as workbook:
            expected = {
                'mizan': ExcelImporter.load_mizan(workbook),
                'bilanco': ExcelImporter.load_bilanco(workbook),
                'gelir_tablosu': ExcelImporter.load_gelir_tablosu(workbook),
            }
        columns = {
            'mizan': ['hesap_kodu', 'hesap_adi', 'hesap_grubu', 'borc', 'alacak', 'borc_bakiye', 'alacak_bakiye'],
            'bilanco': ['tur', 'kalem', 'tutar'],
            'gelir_tablosu': ['kalem', 'tutar'],
        }
        with sqlite3.connect(settings.db_path.as_uri() + '?mode=ro', uri=True) as connection:
            for table, fields in columns.items():
                with self.subTest(table=table):
                    actual = pd.read_sql_query('SELECT ' + ','.join(fields) + ' FROM ' + table, connection)
                    source = expected[table][fields].reset_index(drop=True)
                    pd.testing.assert_frame_equal(actual, source, check_dtype=False, atol=.001, rtol=0)

    def test_index_dimension_is_not_fixed_to_nomic(self):
        ingestor = QdrantIngestor.__new__(QdrantIngestor)
        ingestor.client = Mock()
        ingestor.client.get_collections.return_value.collections = []
        ingestor.collection_name = 'test_only'
        ingestor.recreate_collection(1024)
        self.assertEqual(ingestor.client.create_collection.call_args.kwargs['vectors_config'].size, 1024)
        ingestor.client.delete_collection.assert_not_called()


if __name__ == '__main__':
    unittest.main()
