import os
import glob
import uuid
from typing import List, Dict, Any
from ollama import Client
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from src.config import settings

class QdrantIngestor:
    def __init__(
        self,
        docs_dir: str = "data/mevzuat",
        collection_name: str = settings.collection_name,
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        embed_model: str = settings.embed_model,
        ollama_host: str = "http://127.0.0.1:11434"
    ):
        self.docs_dir = os.path.abspath(docs_dir)
        self.collection_name = collection_name
        self.embed_model = embed_model
        self.ollama_client = Client(host=ollama_host)
        self.client = QdrantClient(host=qdrant_host, port=qdrant_port)

    def recreate_collection(self, vector_size: int) -> None:
        collections = [c.name for c in self.client.get_collections().collections]
        if self.collection_name in collections:
            self.client.delete_collection(collection_name=self.collection_name)
            print(f"Eski '{self.collection_name}' koleksiyonu silindi.")

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
        )
        print(f"Yeni '{self.collection_name}' koleksiyonu temiz olarak oluşturuldu.")

    def _split_into_articles(self, text: str, source_doc: str) -> List[Dict[str, Any]]:
        """Mevzuat maddelerini madde başlıklarıyla birleştirerek bağlam bütünlüğünü korur."""
        lines = text.splitlines()
        chunks = []
        current_title = "Giriş / Genel Esaslar"
        current_lines = []

        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue

            if line_str.upper().startswith("MADDE "):
                if current_lines:
                    chunk_body = "\n".join(current_lines).strip()
                    if chunk_body:
                        chunks.append({
                            "text": f"{current_title}\n{chunk_body}",
                            "metadata": {"source": source_doc, "section": current_title}
                        })
                    current_lines = []
                current_title = line_str
            else:
                current_lines.append(line_str)

        if current_lines:
            chunk_body = "\n".join(current_lines).strip()
            if chunk_body:
                chunks.append({
                    "text": f"{current_title}\n{chunk_body}",
                    "metadata": {"source": source_doc, "section": current_title}
                })

        return chunks

    def run_ingestion(self) -> None:
        txt_files = glob.glob(os.path.join(self.docs_dir, "*.txt"))
        if not txt_files:
            print(f"Uyarı: '{self.docs_dir}' dizininde .txt dosyası bulunamadı.")
            return

        all_chunks = []
        for file_path in txt_files:
            file_name = os.path.basename(file_path)
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            chunks = self._split_into_articles(content, file_name)
            all_chunks.extend(chunks)

        print(f"Toplam {len(all_chunks)} madde bloğu elde edildi. Embedding çıkarılıyor...")

        points = []
        for item in all_chunks:
            response = self.ollama_client.embeddings(
                model=self.embed_model,
                prompt=item["text"]
            )
            points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=response["embedding"],
                    payload={
                        "text": item["text"],
                        "source": item["metadata"]["source"],
                        "section": item["metadata"]["section"]
                    }
                )
            )

        if not points:
            raise ValueError("İndekslenecek mevzuat parçası yok; mevcut koleksiyon korundu.")
        self.recreate_collection(len(points[0].vector))
        self.client.upsert(collection_name=self.collection_name, points=points, wait=True)
        print(f"Başarılı: {len(points)} adet vektör Qdrant'a yüklendi.")

if __name__ == "__main__":
    ingestor = QdrantIngestor()
    ingestor.run_ingestion()
