from pathlib import Path
from pydantic import BaseModel, Field

class Settings(BaseModel):
    """Uygulama genel yapılandırma ve dosya yolları yönetimi."""
    base_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent)
    data_dir: Path = Field(default=None)
    db_path: Path = Field(default=None)
    excel_path: Path = Field(default=None)
    llm_model: str = "qwen2.5:7b-instruct-q4_K_M"
    embed_model: str = "bge-m3"
    collection_name: str = "epdk_mevzuat_bge_m3"
    ollama_host: str = "http://127.0.0.1:11434"
    num_ctx: int = Field(default=2048, ge=512)
    num_predict: int = Field(default=768, ge=1)
    request_timeout: float = Field(default=120.0, gt=0)

    def model_post_init(self, __context):
        if self.data_dir is None:
            self.data_dir = self.base_dir / "data"
        if self.db_path is None:
            self.db_path = self.base_dir / "db" / "financial.db"
        if self.excel_path is None:
            self.excel_path = self.data_dir / "mizan_bilanco_dummy_2024.xlsx"

settings = Settings()
