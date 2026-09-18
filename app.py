import streamlit as st
import time
import uuid
from src.access import require_access
from src.audit import record
from src.chains import RAGPipeline

st.set_page_config(
    page_title="Finans & EPDK Mevzuat Asistanı v2",
    page_icon="⚖️",
    layout="wide"
)

require_access(st)

# Pipeline ve Motoru Başlatma
def get_pipeline():
    # Konuşma belleği kullanıcı oturumuna aittir.
    if st.session_state.get("pipeline_revision") != "accuracy-2026-09-17-r10":
        st.session_state.pipeline = RAGPipeline()
        st.session_state.pipeline_revision = "accuracy-2026-09-17-r10"
    return st.session_state.pipeline

pipeline = get_pipeline()
finance_engine = pipeline.finance_engine

# Kenar Çubuğu
st.sidebar.title("Kurumsal Finans Paneli")
st.sidebar.caption("Deterministik Veri & Sistem Durumu")

if st.sidebar.button("Bilanço Denkliğini Doğrula", width="stretch"):
    bs_data = finance_engine.verify_balance_sheet()
    if bs_data["denk_mi"]:
        st.sidebar.success(f"Bilanço Denk: {bs_data['toplam_aktif']:,.2f} TL")
    else:
        st.sidebar.error(
            f"Denklik Bozuk!\n"
            f"Aktif: {bs_data['toplam_aktif']:,.2f} TL\n"
            f"Pasif: {bs_data['toplam_pasif']:,.2f} TL\n"
            f"Fark: {bs_data.get('fark', 0.0):,.2f} TL"
        )

with st.sidebar.expander("Mizan Hesaplarını İncele"):
    df_mizan = finance_engine.get_all_accounts()
    st.dataframe(df_mizan[["hesap_kodu", "hesap_adi", "borc_bakiye", "alacak_bakiye"]], width="stretch")

if st.sidebar.button("Sohbet Geçmişini Sıfırla", width="stretch"):
    st.session_state.messages = []
    pipeline.memory.clear()
    st.rerun()

# Ana Ekran
st.title("⚖️ Finans & EPDK Mevzuat Asistanı")
st.caption("Hibrit Mimari: Deterministik SQLite Finans Motoru + Qdrant Vektör Arama (Qwen 2.5)")
st.sidebar.caption(f"Yerel model: {pipeline.llm_model}")
st.caption("Test ortamı: veriler ve mevzuat metinleri kurgusaldır.")

def render_sources(sources):
    """Show human-readable evidence labels; never expose SQL or application code."""
    with st.expander("📌 Kaynaklar"):
        for i, src in enumerate(sources, 1):
            source_file = src.get('source', 'Kaynak')
            raw_section = src.get('section', 'İlgili bölüm')
            clean_section = raw_section.split("(")[0].strip()
            st.markdown(f"**{i}. {source_file}** — {clean_section}")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Geçmiş Mesajlar
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg.get("badge") == "ERROR":
            st.error(msg["content"])
        else:
            st.markdown(msg["content"])
        if "badge" in msg:
            st.caption(f"İşlem Kanalı: **{msg['badge']}**")
        if msg.get("sources"):
            render_sources(msg["sources"])

# Kullanıcı Girişi
prompt = st.chat_input("Bir finansal hesap veya EPDK mevzuat sorusu sorun...")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Sorgu sınıflandırılıyor ve yanıt üretiliyor..."):
            previous_messages = [m for m in st.session_state.messages[:-1] if m.get("badge") != "ERROR"]
            started = time.perf_counter()
            result = pipeline.ask(prompt, chat_history=previous_messages)
            if '_audit_session' not in st.session_state:
                st.session_state['_audit_session'] = str(uuid.uuid4())
            try:
                record(prompt, result, time.perf_counter()-started, st.session_state['_audit_session'],
                       username=st.session_state.get('_username'))
            except OSError:
                st.warning('Yanıt üretildi ancak yerel sorgu kaydı yazılamadı. Disk alanını ve dosya izinlerini kontrol edin.')
            channel = result.get("type", "BİLİNMİYOR")
            answer = result.get("answer", "")
            sources = result.get("sources", [])

            if channel == "ERROR":
                st.error(answer)
            else:
                st.markdown(answer)
            st.caption(f"İşlem Kanalı: **{channel}**")

            if sources:
                render_sources(sources)

            st.session_state.messages.append({
                "role": "assistant",
                "content": answer,
                "badge": channel,
                "sources": sources,
                **({"domain_context": result["domain_context"]} if "domain_context" in result else {}),
                **({"finance_views": result["finance_views"]} if "finance_views" in result else {}),
                **({"history_result": result["history_result"]} if "history_result" in result else {})
            })
