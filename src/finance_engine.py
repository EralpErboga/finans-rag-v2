import os
import re
import sqlite3
import pandas as pd
from typing import Dict, Any, List, Optional
from pathlib import Path

def clean_col_name(c: Any) -> str:
    """Excel başlıklarını standart ASCII snake_case formatına çevirir."""
    val = str(c).strip()
    tr_map = str.maketrans({
        'İ': 'i', 'I': 'i', 'ı': 'i',
        'Ğ': 'g', 'ğ': 'g',
        'Ü': 'u', 'ü': 'u',
        'Ş': 's', 'ş': 's',
        'Ö': 'o', 'ö': 'o',
        'Ç': 'c', 'ç': 'c'
    })
    val = val.translate(tr_map).lower()
    val = re.sub(r'[^a-z0-9_]+', '_', val)
    return val.strip('_')

class FinancialRepository:
    """SQLite veritabanı işlemlerini, bağlantı yönetimini ve şema yönetimini üstlenir."""
    def __init__(self, db_path: str):
        self.db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_schema()

    def get_connection(self, read_only: bool = False) -> sqlite3.Connection:
        if read_only:
            uri = f"file:{self.db_path}?mode=ro"
            conn = sqlite3.connect(uri, uri=True)
        else:
            conn = sqlite3.connect(self.db_path)

        # SQLite içindeki LOWER fonksiyonunu Türkçe karakterlerle tam uyumlu hale getiriyoruz
        def tr_lower(val):
            if val is None:
                return ""
            return str(val).replace("İ", "i").replace("I", "ı").replace("Ö", "ö").replace("Ü", "ü").replace("Ş", "ş").replace("Ç", "ç").replace("Ğ", "ğ").lower()

        conn.create_function("LOWER", 1, tr_lower)
        return conn

    def _init_schema(self) -> None:
        """Tabloları birincil anahtar (Primary Key) ve tiplerle kurumsal olarak oluşturur."""
        with self.get_connection(read_only=False) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mizan (
                    hesap_kodu TEXT PRIMARY KEY,
                    hesap_adi TEXT NOT NULL,
                    hesap_grubu TEXT,
                    borc REAL DEFAULT 0.0,
                    alacak REAL DEFAULT 0.0,
                    borc_bakiye REAL DEFAULT 0.0,
                    alacak_bakiye REAL DEFAULT 0.0
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bilanco (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tur TEXT NOT NULL,
                    kalem TEXT NOT NULL,
                    tutar REAL DEFAULT 0.0
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS gelir_tablosu (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kalem TEXT NOT NULL,
                    tutar REAL DEFAULT 0.0
                );
            """)
            conn.commit()


class ExcelImporter:
    """Excel dosyalarını okuyan, doğrulayan (Validation) ve normalize eden importer katmanı."""
    @staticmethod
    def normalize_code(val: Any) -> str:
        if pd.isna(val) or val is None:
            return ""
        return re.sub(r'\.0+$', '', str(val).strip())

    @classmethod
    def load_mizan(cls, xls: pd.ExcelFile) -> pd.DataFrame:
        df = pd.read_excel(xls, sheet_name="Mizan", header=4)
        df.columns = [clean_col_name(c) for c in df.columns]

        # Olası alternatif kolon adlarını standartlaştır
        col_rename = {
            'hesap_kodu': 'hesap_kodu',
            'kod': 'hesap_kodu',
            'hesap_adi': 'hesap_adi',
            'ad': 'hesap_adi',
            'borc_bakiye': 'borc_bakiye',
            'alacak_bakiye': 'alacak_bakiye'
        }
        df = df.rename(columns=col_rename)

        required = {'hesap_kodu', 'hesap_adi', 'borc_bakiye', 'alacak_bakiye'}
        if not required.issubset(df.columns):
            raise ValueError(f"Mizan şablonu geçersiz. Mevcut kolonlar: {list(df.columns)}, Beklenenler: {required}")

        df = df.dropna(subset=['hesap_kodu']).copy()
        df['hesap_kodu'] = df['hesap_kodu'].apply(cls.normalize_code)
        df['hesap_adi'] = df['hesap_adi'].astype(str).str.strip()
        df['hesap_grubu'] = df['hesap_grubu'].astype(str).str.strip() if 'hesap_grubu' in df.columns else ""

        for col in ['borc', 'alacak', 'borc_bakiye', 'alacak_bakiye']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

        return df.drop_duplicates(subset=['hesap_kodu'])

    @classmethod
    def load_bilanco(cls, xls: pd.ExcelFile) -> pd.DataFrame:
        df_raw = pd.read_excel(xls, sheet_name="Bilanço", header=2)
        df_aktif = df_raw.iloc[:, [0, 1]].dropna(subset=[df_raw.columns[0]]).copy()
        df_aktif.columns = ['kalem', 'tutar']
        df_aktif['tur'] = 'AKTIF'

        df_pasif = df_raw.iloc[:, [2, 3]].dropna(subset=[df_raw.columns[2]]).copy()
        df_pasif.columns = ['kalem', 'tutar']
        df_pasif['tur'] = 'PASIF'

        df = pd.concat([df_aktif, df_pasif], ignore_index=True)
        df['kalem'] = df['kalem'].astype(str).str.strip()
        df['tutar'] = pd.to_numeric(df['tutar'], errors='coerce').fillna(0.0)
        return df

    @classmethod
    def load_gelir_tablosu(cls, xls: pd.ExcelFile) -> pd.DataFrame:
        df = pd.read_excel(xls, sheet_name="Gelir Tablosu", header=2).dropna(how='all').copy()
        df.columns = ['kalem', 'tutar']
        df['kalem'] = df['kalem'].astype(str).str.strip()
        df['tutar'] = pd.to_numeric(df['tutar'], errors='coerce').fillna(0.0)
        return df


class FinanceEngine:
    """Kurumsal RAG hattına deterministik SQL verisi sağlayan birleşik finans motoru."""
    def __init__(self, excel_path: str = "data/mizan_bilanco_dummy_2024.xlsx", db_path: str = "db/financial.db"):
        self.excel_path = os.path.abspath(excel_path)
        if not os.path.exists(self.excel_path) and os.path.exists("mizan_bilanco_dummy_2024.xlsx"):
            self.excel_path = os.path.abspath("mizan_bilanco_dummy_2024.xlsx")

        self.repository = FinancialRepository(db_path)
        self._sync_database_if_needed()

    def _sync_database_if_needed(self) -> None:
        with self.repository.get_connection(read_only=False) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM mizan")
            count = cursor.fetchone()[0]

            if count > 0:
                return

            if not os.path.exists(self.excel_path):
                raise FileNotFoundError(f"Excel dosyası bulunamadı: {self.excel_path}")

            xls = pd.ExcelFile(self.excel_path)
            df_mizan = ExcelImporter.load_mizan(xls)
            df_bilanco = ExcelImporter.load_bilanco(xls)
            df_gelir = ExcelImporter.load_gelir_tablosu(xls)

            try:
                df_mizan[['hesap_kodu', 'hesap_adi', 'hesap_grubu', 'borc', 'alacak', 'borc_bakiye', 'alacak_bakiye']].to_sql(
                    "mizan", conn, if_exists="append", index=False
                )
                df_bilanco[['tur', 'kalem', 'tutar']].to_sql("bilanco", conn, if_exists="append", index=False)
                df_gelir[['kalem', 'tutar']].to_sql("gelir_tablosu", conn, if_exists="append", index=False)
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise RuntimeError(f"Finansal veri içe aktarma hatası: {str(e)}")

    def execute_sql(self, query: str, params=None) -> Dict[str, Any]:
        clean_query = query.strip()
        if not re.match(r"^SELECT\b", clean_query, re.IGNORECASE):
            return {"status": "error", "message": "Yalnızca SELECT sorgularına izin verilir."}
        try:
            with self.repository.get_connection(read_only=True) as conn:
                df = pd.read_sql_query(clean_query, conn, params=params)
                records = df.astype(object).where(pd.notnull(df), None).to_dict(orient="records")
                return {"status": "success", "data": records, "columns": list(df.columns)}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def sum_account_balances(self, codes):
        """Explicit account lists are parameterized, never interpreted as a range."""
        codes = list(dict.fromkeys(codes))
        placeholders = ", ".join("?" for _ in codes)
        sql = f"""SELECT CASE WHEN COUNT(DISTINCT hesap_kodu) = ? THEN
            SUM(CASE WHEN substr(hesap_kodu, 1, 1) IN ('3','4','5')
            THEN alacak_bakiye - borc_bakiye
            WHEN substr(hesap_kodu, 1, 1) = '6' THEN ABS(borc_bakiye - alacak_bakiye)
            ELSE borc_bakiye - alacak_bakiye END)
            ELSE NULL END AS toplam_bakiye FROM mizan WHERE hesap_kodu IN ({placeholders})"""
        result = self.execute_sql(sql, [len(codes), *codes])
        result.update(sql=sql, parameters=[len(codes), *codes])
        return result

    def match_account_names(self, question):
        """Only full catalogue names match; no question/answer fixtures."""
        from src.retrieval import terms
        query_terms = set(terms(question.replace('â', 'a')))
        names = self.execute_sql("SELECT hesap_kodu, hesap_adi FROM mizan")
        matches = []
        for row in names.get("data", []):
            # Parantez içindeki açıklamaları zorunlu arama sözcüğü sayma.
            name = row["hesap_adi"].split("(")[0].strip()
            required = set(terms(name.replace('â', 'a')))
            if required and required.issubset(query_terms):
                matches.append(row["hesap_kodu"])
        return matches

    def account_balances(self, codes):
        placeholders = ', '.join('?' for _ in codes)
        sql = f"SELECT hesap_kodu, hesap_adi, ABS(borc_bakiye-alacak_bakiye) AS bakiye FROM mizan WHERE hesap_kodu IN ({placeholders})"
        result = self.execute_sql(sql, codes)
        result.update(sql=sql, parameters=codes)
        return result

    def get_database_schema(self) -> str:
        """
        Tabloların DDL şemasını ve dinamik DISTINCT değer kataloğunu (Entity Linking) döner.
        """
        with self.repository.get_connection(read_only=True) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence';")
            tables = cursor.fetchall()

            schema_blocks = []
            for tbl_name, tbl_ddl in tables:
                block = f"-- TABLO: {tbl_name}\n{tbl_ddl}"

                if tbl_name == "mizan":
                    cursor.execute("SELECT hesap_kodu, hesap_adi FROM mizan ORDER BY hesap_kodu")
                    hesaplar = [f"{code}: {name}" for code, name in cursor.fetchall()]
                    block += f"\n-- MİZAN HESAP KODU VE ADI EŞLEŞMELERİ (yalnızca bu kodları kullan):\n-- {hesaplar}"

                elif tbl_name == "gelir_tablosu":
                    cursor.execute("SELECT DISTINCT kalem FROM gelir_tablosu WHERE kalem IS NOT NULL AND kalem != ''")
                    distinct_kalemler = [row[0] for row in cursor.fetchall()]
                    block += f"\n-- '{tbl_name}.kalem' GEÇERLİ DEĞERLER (Literal Values):\n-- {distinct_kalemler}"

                elif tbl_name == "bilanco":
                    cursor.execute("SELECT DISTINCT kalem FROM bilanco WHERE kalem IS NOT NULL AND kalem != ''")
                    distinct_bilanco = [row[0] for row in cursor.fetchall()]
                    block += f"\n-- '{tbl_name}.kalem' GEÇERLİ DEĞERLER (Literal Values):\n-- {distinct_bilanco}"

                schema_blocks.append(block)

            return "\n\n".join(schema_blocks)

    def get_finance_catalog(self) -> List[Dict[str, Any]]:
        """Return the only records a language-model plan may select."""
        catalog = []
        queries = (
            ("mizan", "SELECT hesap_kodu AS key, hesap_adi AS label FROM mizan ORDER BY hesap_kodu"),
            ("bilanco", "SELECT CAST(id AS TEXT) AS key, kalem AS label FROM bilanco ORDER BY id"),
            ("gelir_tablosu", "SELECT CAST(id AS TEXT) AS key, kalem AS label FROM gelir_tablosu ORDER BY id"),
        )
        for source, query in queries:
            result = self.execute_sql(query)
            if result.get("status") != "success":
                raise RuntimeError(f"{source} kataloğu okunamadı: {result.get('message', '')}")
            for row in result["data"]:
                catalog.append({
                    "id": f"{source}:{row['key']}",
                    "source": source,
                    "key": str(row["key"]),
                    "label": row["label"],
                })
        return catalog

    @staticmethod
    def _account_value(row: Dict[str, Any]) -> float:
        return abs(float(row.get("borc_bakiye", 0.0)) - float(row.get("alacak_bakiye", 0.0)))

    def execute_finance_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a declarative plan and perform every calculation in code."""
        allowed_operations = {"lookup", "sum", "compare", "ratio", "balance_check"}
        operation = plan.get("operation")
        item_ids = plan.get("items", [])
        if operation not in allowed_operations:
            raise ValueError("Desteklenmeyen mali işlem planı.")
        if operation == "balance_check":
            check = self.verify_balance_sheet()
            return {
                "status": "success", "operation": operation,
                "data": [{
                    "label": "Toplam aktif", "value": check["toplam_aktif"], "source": "bilanco",
                    "source_label": "TOPLAM AKTİF",
                }, {
                    "label": "Toplam pasif", "value": check["toplam_pasif"], "source": "bilanco",
                    "source_label": "TOPLAM PASİF",
                }, {
                    "label": "Fark", "value": check["fark"], "source": "hesaplama",
                    "source_label": "Aktif - pasif denklik kontrolü",
                }],
                "equal": check["denk_mi"],
            }
        if not isinstance(item_ids, list) or not 1 <= len(item_ids) <= 8:
            raise ValueError("Mali işlem için 1-8 katalog kalemi seçilmelidir.")
        catalog = {item["id"]: item for item in self.get_finance_catalog()}
        if any(not isinstance(item_id, str) or item_id not in catalog for item_id in item_ids):
            raise ValueError("Plan, katalogda bulunmayan bir mali kalem seçti.")
        # Sırayı koru ve aynı kalemi iki kez sayma.
        selected = [catalog[item_id] for item_id in dict.fromkeys(item_ids)]
        rows = []
        for item in selected:
            if item["source"] == "mizan":
                result = self.execute_sql(
                    "SELECT hesap_kodu, hesap_adi, borc_bakiye, alacak_bakiye "
                    "FROM mizan WHERE hesap_kodu = ?", [item["key"]])
                if not result.get("data"):
                    raise ValueError(f"{item['id']} kaydı bulunamadı.")
                value = self._account_value(result["data"][0])
            elif item["source"] == "bilanco":
                result = self.execute_sql("SELECT tutar FROM bilanco WHERE id = ?", [item["key"]])
                if not result.get("data"):
                    raise ValueError(f"{item['id']} kaydı bulunamadı.")
                value = abs(float(result["data"][0]["tutar"]))
            else:
                result = self.execute_sql("SELECT tutar FROM gelir_tablosu WHERE id = ?", [item["key"]])
                if not result.get("data"):
                    raise ValueError(f"{item['id']} kaydı bulunamadı.")
                value = abs(float(result["data"][0]["tutar"]))
            rows.append({
                "id": item["id"], "label": item["label"], "value": value,
                "source": item["source"], "source_label": item["label"],
                "account_code": item["key"] if item["source"] == "mizan" else None,
            })
        output = {"status": "success", "operation": operation, "data": rows}
        values = [row["value"] for row in rows]
        if operation == "sum":
            output["calculation"] = {"label": "Toplam", "value": sum(values)}
        elif operation == "compare" and len(values) >= 2:
            output["calculation"] = {"label": "Fark", "value": values[0] - values[1]}
        elif operation == "ratio":
            if len(values) != 2:
                raise ValueError("Oran işlemi pay ve payda olmak üzere iki kalem gerektirir.")
            if values[1] == 0:
                raise ValueError("Payda sıfır olduğu için oran hesaplanamadı.")
            output["calculation"] = {"label": "Oran", "value": values[0] / values[1], "unit": "ratio"}
        return output

    def get_context_records(self, question: str, limit: int = 6) -> Dict[str, Any]:
        """Hibrit açıklama için gerçek satırları getirir; modelden oran/SQL uydurmasını istemez."""
        from src.retrieval import rerank, terms
        sql = """SELECT 'mizan' AS kaynak, hesap_kodu, hesap_adi AS kalem,
                 borc_bakiye, alacak_bakiye,
                 ABS(borc_bakiye-alacak_bakiye) AS tutar
                 FROM mizan
                 UNION ALL SELECT 'bilanco', NULL, kalem, NULL, NULL, tutar FROM bilanco
                 UNION ALL SELECT 'gelir_tablosu', NULL, kalem, NULL, NULL, tutar FROM gelir_tablosu"""
        result = self.execute_sql(sql)
        if result.get("status") != "success":
            return result
        query_terms = set(terms(question))
        codes = set(re.findall(r"\b\d{3}\b", question))
        candidates = []
        for row in result["data"]:
            text = f"{row['hesap_kodu'] or ''} {row['kalem']}"
            if query_terms.intersection(terms(text)):
                candidates.append({"text": text, "score": 0.0, "row": row})
        ranked = rerank(question, candidates, len(candidates))
        ranked.sort(key=lambda item: item["row"]["hesap_kodu"] in codes, reverse=True)
        return {"status": "success", "data": [item["row"] for item in ranked[:limit]],
                "sql": sql, "selection": "Soru ile sözcük eşleşmesi; hesaplanmış etki değildir."}

    def verify_balance_sheet(self) -> Dict[str, Any]:
        res = self.execute_sql("SELECT tur, tutar FROM bilanco WHERE LOWER(kalem) LIKE '%toplam%'")
        if res["status"] != "success" or not res["data"]:
            return {"denk_mi": False, "toplam_aktif": 0.0, "toplam_pasif": 0.0, "fark": 0.0}

        aktif = sum(float(r["tutar"]) for r in res["data"] if str(r["tur"]).upper() == "AKTIF")
        pasif = sum(float(r["tutar"]) for r in res["data"] if str(r["tur"]).upper() == "PASIF")

        fark = abs(aktif - pasif)
        return {
            "toplam_aktif": aktif,
            "toplam_pasif": pasif,
            "fark": fark,
            "denk_mi": (fark < 0.01 and aktif > 0)
        }

    def get_all_accounts(self) -> pd.DataFrame:
        with self.repository.get_connection(read_only=True) as conn:
            return pd.read_sql_query("SELECT hesap_kodu, hesap_adi, borc_bakiye, alacak_bakiye FROM mizan ORDER BY hesap_kodu ASC", conn)

    def query_account(self, account_code: str) -> Dict[str, Any]:
        """Belirli bir hesap kodunu mizan tablosundan sorgular ve net bakiye analizini döner."""
        clean_code = str(account_code).strip()
        sql = f"SELECT hesap_kodu, hesap_adi, borc_bakiye, alacak_bakiye FROM mizan WHERE hesap_kodu = '{clean_code}';"
        res = self.execute_sql(sql)

        if res["status"] != "success" or not res["data"]:
            return {"status": "error", "message": f"{clean_code} kodlu hesap bulunamadı."}

        row = res["data"][0]
        borc = float(row.get("borc_bakiye", 0.0))
        alacak = float(row.get("alacak_bakiye", 0.0))

        net_bakiye = borc if borc > 0 else alacak
        bakiye_tipi = "Borç Bakiyesi" if borc > 0 else "Alacak Bakiyesi"

        return {
            "status": "success",
            "records": [row],
            "net_bakiye": net_bakiye,
            "bakiye_tipi": bakiye_tipi
        }
