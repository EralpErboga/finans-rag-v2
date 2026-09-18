# Finans RAG v2

Bu projede hedefim, örnek mizan/bilanço verileri ve kurgusal EPDK metinleri üzerinde yerel çalışan bir finans asistanı geliştirmek. Arayüz için Streamlit kullanılıyor.
Varsayılan yanıt modeli `qwen2.5:7b-instruct-q4_K_M`, embedding modeli `bge-m3`tır.
Modeller Ollama üzerinden bu bilgisayarda çalışır; Qdrant ve SQLite yereldir.

## Teslim belgeleri

- [Kurulum ve kullanım kılavuzu](docs/KURULUM_VE_KULLANIM.md)
- [Teknik rapor](docs/TEKNIK_RAPOR.md)
- [Sunum ve demo senaryosu](docs/SUNUM_VE_DEMO.md)
- [Doğrulama sonuçları](docs/DOGRULAMA.md)
- [Teslim içeriği](docs/TESLIM.md)

18 Eylül sürümünde kişisel kullanıcı adı ve şifreyle giriş yapılır.
Önceki uygulama parolası **Yeni kullanıcı oluştur** ekranındaki kayıt anahtarıdır.
Hesabınızı oluşturup kurtarma kodunu saklayın. Giriş ekranında **Şifremi unuttum**,
girişten sonra yan panelde **Şifre değiştir** bulunur.

## Kurulum

Python 3.11, Ollama ve Docker Desktop gereklidir. Komutları proje klasöründe PowerShell ile çalıştırın.

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
$env:OLLAMA_HOST = '127.0.0.1:11434'
ollama pull qwen2.5:7b-instruct-q4_K_M
ollama pull bge-m3
docker compose up -d qdrant
```

Ollama kapalıysa model indirmeden önce ayrı bir PowerShell penceresinde başlatın:

```powershell
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_NUM_PARALLEL = '1'
$env:OLLAMA_MAX_LOADED_MODELS = '1'
$env:OLLAMA_NO_CLOUD = '1'
ollama serve
```

Qdrant verisi `db/qdrant_storage` altında korunur. Mevcut koleksiyonu kullanın.
Yalnızca ilk kurulumda koleksiyon yoksa `python -m src.ingest_qdrant` çalıştırın:
bu komut mevcut `epdk_mevzuat_bge_m3` koleksiyonunu silip yeniden oluşturur.
Eski Nomic koleksiyonu `epdk_mevzuat` bu komuttan etkilenmez.
Embedding modelini değiştirmek yeniden indeksleme gerektirir.

## Çalıştırma

Yeni kurulumda `.\venv\Scripts\python.exe setup_access.py` ile kayıt anahtarı ve izinli ağı belirleyin.
Mevcut yapılandırmanız varsa tekrar çalıştırmanız gerekmez. Bu komut kişisel hesap şifresini değiştirmez.
Parola, ağ sınırı ve log saklama ayrıntıları: [Erişim ve yerel kayıt](ACCESS_AND_LOGS.md).
Günlük kullanım için `.\start_app.ps1` kullanın. Kurum ağına açılış bu belgede
anlatılan gerçek CIDR ve TLS yapılandırmasını gerektirir.

Docker Desktop ve Ollama açıkken:

```powershell
docker compose up -d qdrant
.\venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false
```

Tarayıcı: http://127.0.0.1:8501

Model, bağlam ve zaman aşımı ayarları `src/config.py` içindedir.
Varsayılan bağlam 2048 token, en uzun yanıt 768 token, istek zaman aşımı 120 saniyedir.
Ollama kullanılabilir GPU/RAM'e göre yerleşimi seçer. `ollama ps` aktif model yerleşimini gösterir.
Model çağrıları aynı 2K bağlamı kullanır. GPU katman sayısı sabitlenmemiştir.

## Kontroller

```powershell
$env:PYTHONUTF8 = '1'
.\venv\Scripts\python.exe -m unittest test_runtime_errors -v
.\venv\Scripts\python.exe -m unittest test_general_capabilities -v
.\venv\Scripts\python.exe test_engine.py
.\venv\Scripts\python.exe test_pipeline.py
.\venv\Scripts\python.exe test_router.py
.\venv\Scripts\python.exe test_generalization.py --report review_artifacts/generalization_latest.json
```

Unittest kontrolleri ve test_engine.py canlı LLM gerektirmez. Diğer testler yerel Ollama modelleri ve Qdrant'a ihtiyaç duyar.
Canlı testler doğru sonuçları denetler; başarısızlıkta sıfırdan farklı işlem koduyla sonlanır.
Yeni makinede kalite ve süreler tekrar ölçülmelidir. Birkaç kabul testinin geçmesi tüm soruların doğruluğunu kanıtlamaz.

Örnek sorular: “Kasa hesabının bakiyesi ne kadar?”, “2024 yılı toplam genel yönetim gideri ne kadar?”,
“A grubu bölgelerde kayıp-kaçak hedef üst sınırı nedir?”

## Bilinen sınırlar

- Açık sayılı soru/kelime seçimi ve desteklenen listeleme ifadeleri modelsiz
  çalışır; diğer geçmiş ifadeleri yerel model planlamasına gider. İfade araması
  sözcük başlangıcından eşleşir ve ekleri tolere eder; sözcük ortasını eşleştirmez.

- Prototip gerçek mevzuat veya gerçek şirket verisi içermez.
- Model yürütülebilir SQL üretmez; kapalı katalogdan kalem ve işlem seçer. Parametreli SQL ve hesaplamalar Python tarafından yürütülür. Kalem/niyet seçiminin her serbest ifadede doğru olması garanti değildir.
- Model/servis hataları `ERROR` olarak gösterilir; bunlar kapsam dışı soru veya veri yokluğu sayılmaz.
- 7B varsayılandır. Ryzen 7 3750H + GTX 1660 Ti Max-Q 6 GB üzerinde GPU/CPU karma yerleşimle çalıştırıldı.
  Boş RAM'e göre açılış ve yanıt süreleri değişir. Kurulu 3B model kaldırılmadı; önceki kalite testlerinde hatalar verdi.
- Excel içeri aktarma mevcut veritabanını otomatik güncellemez.
- Compose yalnızca Qdrant'ı kapsar; bu aşamada kurumsal kimlik doğrulama ve üretim dağıtımı bulunmaz.
- Model dosya boyutu, toplam çalışma belleği gereksinimine eşit değildir. Önceki bellek hatası tek başına işlemcinin modeli çalıştıramayacağını kanıtlamaz.

## Çalışma mantığı

- Bağımsız sorular geçmiş konuya zorla bağlanmaz; kısa takip girdileri geçmişle çözümlenir.
- Sohbet listesini, belirli soru sırasını, kelime sırasını ve önceki sıra referansını desteklenen ifadelerde Python hesaplar.
  Diğer ifadeler modele gider; her Türkçe ifade biçimi garanti edilmez.
- Mevzuat araması Qdrant'taki en iyi 20 vektör adayını hafif sözcük eşleştirmesiyle yeniden sıralar.
  Bu küçük corpus çözümüdür; büyük koleksiyonlarda tam bir BM25 indeksi değildir.
- Mali tutarlar ve oranlar kodla hesaplanır; yanıtın sayı, birim ve kalem eşleşmesi denetlenir. Desteklenen mali takipler önceki yanıtta seçilmiş kayıt kimliklerini kullanır.
- Açık hesap kodları doğrudan katalogda doğrulanır. Brüt/net çiftleri kaynak etiketlerinden eşleştirilir; modelin karşılık hesabını brüt tutar yerine seçmesi engellenir.
- Hibrit analiz mali katalog planı ve kaynak metinlerini birlikte gösterir. Bu veritabanında teknik ölçüm veya idari onay kayıtları bulunmadığından kesin uygunluk ya da yaptırım tutarı çıkarılmaz.
- Hibrit bölüm şu aşamada güvenli kanıt görünümüdür: mali kayıt + kaynak maddesi + yeterlilik sınırı gösterir.
  Yerel modelin doğrulanmamış oran/ceza hesabı ürettiği görüldüğünden serbest sayısal sentez kapatılmıştır.
  Tam otomatik hibrit hesaplama için ayrıca doğrulanmış hesaplama planları ve teknik/idari veri gerekir.
- Arayüzde belge, bölüm ve hesap kaynakları gösterilir; SQL veya uygulama kodu gösterilmez. Kaynak bulunması, seçilen kaynağın soruya uygunluğunu tek başına kanıtlamaz.

## Sunum ve kılavuz

- [PowerPoint sunumu](docs/teslim/Finans_RAG_v2_Sunum.pptx)
- [Ekran görüntülü kılavuz](docs/teslim/Finans_RAG_v2_Ekran_Goruntulu_Kilavuz.pdf)

## Sunum ve kılavuz

- [PowerPoint sunumu](docs/teslim/Finans_RAG_v2_Sunum.pptx)
- [Ekran görüntülü kılavuz](docs/teslim/Finans_RAG_v2_Ekran_Goruntulu_Kilavuz.pdf)
