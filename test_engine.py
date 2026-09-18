from src.finance_engine import FinanceEngine

def run_tests():
    print("1. Finans Motoru başlatılıyor ve SQLite veritabanı kuruluyor...")
    engine = FinanceEngine()
    print("-> Veritabanı başarıyla oluşturuldu/güncellendi.\n")

    print("2. '100' Kasa hesabı test ediliyor...")
    kasa = engine.query_account("100")
    assert kasa["status"] == "success", "Kasa hesabı bulunamadı!"
    print(f"-> Kasa Hesabı: {kasa['records'][0]['hesap_adi']}")
    print(f"-> Net Bakiye: {kasa['net_bakiye']:,.2f} TL ({kasa['bakiye_tipi']})\n")

    print("3. '102' Bankalar hesabı test ediliyor...")
    banka = engine.query_account("102")
    assert banka["status"] == "success", "Bankalar hesabı bulunamadı!"
    print(f"-> Net Bakiye: {banka['net_bakiye']:,.2f} TL ({banka['bakiye_tipi']})\n")

    print("4. Bilanço denkliği kontrol ediliyor...")
    bilanco = engine.verify_balance_sheet()
    print(f"-> Toplam Aktif: {bilanco['toplam_aktif']:,.2f} TL")
    print(f"-> Toplam Pasif: {bilanco['toplam_pasif']:,.2f} TL")
    assert bilanco["denk_mi"] is True, "Bilanço denkliği sağlanamadı!"
    print("-> Bilanço Denkliği: BAŞARILI (Aktif = Pasif)\n")

    print("Tüm finans motoru testleri başarıyla tamamlandı.")

if __name__ == "__main__":
    run_tests()