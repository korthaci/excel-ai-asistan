import streamlit as st
import pandas as pd
import os
import sqlite3
from openai import OpenAI
from dotenv import load_dotenv

# --- 1. AYARLAR & API ---
load_dotenv()
st.set_page_config(page_title="Finans Asistanı", layout="wide")

@st.cache_resource
def get_client():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        st.error("GROQ_API_KEY bulunamadı (.env dosyasını kontrol et).")
        return None
    return OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")

client = get_client()

# --- 2. VERİTABANI YÖNETİMİ (SQLite) ---
# Dosyaları kaydetmek için yerel bir veritabanı oluşturuyoruz
def init_db():
    conn = sqlite3.connect('sheets.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS sheets (id INTEGER PRIMARY KEY, name TEXT, url TEXT)''')
    conn.commit()
    conn.close()

def get_sheets():
    conn = sqlite3.connect('sheets.db')
    c = conn.cursor()
    c.execute("SELECT id, name, url FROM sheets")
    data = c.fetchall()
    conn.close()
    return data

def add_sheet(name, url):
    conn = sqlite3.connect('sheets.db')
    c = conn.cursor()
    c.execute("INSERT INTO sheets (name, url) VALUES (?, ?)", (name, url))
    conn.commit()
    conn.close()

def delete_sheet(sheet_id):
    conn = sqlite3.connect('sheets.db')
    c = conn.cursor()
    c.execute("DELETE FROM sheets WHERE id=?", (sheet_id,))
    conn.commit()
    conn.close()

# Veritabanını başlat ve varsayılan linki kontrol et
init_db()
default_name = "Ana Finans Tablosu (Varsayılan)"
default_url = "https://docs.google.com/spreadsheets/d/109p_A1AW4phVCDol24uOWNV6cxh_9leL"

# Eğer veritabanı boşsa, verdiğin linki ekle
sheets_list = get_sheets()
if not sheets_list:
    add_sheet(default_name, default_url)
    sheets_list = get_sheets()

# --- 3. KENAR ÇUBUĞU (DOSYA YÖNETİMİ) ---
with st.sidebar:
    st.header("📂 Dosya Yöneticisi")
    
    # Mevcut dosyaları listeleme
    sheet_options = {row[1]: row[2] for row in sheets_list} # {Name: URL}
    
    if sheet_options:
        selected_name = st.selectbox("İncelenecek Dosya:", list(sheet_options.keys()))
        current_url = sheet_options[selected_name]
        
        st.success(f"Seçilen: {selected_name}")
        
        # Yeni Dosya Ekleme
        st.divider()
        with st.expander("➕ Yeni Dosya Ekle"):
            new_name = st.text_input("Dosya Adı")
            new_url = st.text_input("Google Sheets Linki")
            if st.button("Ekle"):
                if new_name and new_url:
                    add_sheet(new_name, new_url)
                    st.rerun() # Listeyi yenile
        
        # Dosya Silme (Geliştirici için basit tutuldu)
        with st.expander("🗑️ Dosya Sil"):
            # Mevcutları ID ile listele
            for sheet_id, name, url in sheets_list:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.text(name)
                with col2:
                    if st.button("Sil", key=f"del_{sheet_id}"):
                        delete_sheet(sheet_id)
                        st.rerun()

# --- 4. VERİ YÜKLEME MANTIĞI ---
# Otomatik olarak seçili dosyayı yükle
df = None
data_text = ""

try:
    if current_url:
        sheet_id = current_url.split("/d/")[1].split("/")[0]
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        
        # Veriyi Session State'e kaydet ki her render'da tekrar tekrar indirmesin
        if "active_data" not in st.session_state or st.session_state["active_url"] != current_url:
            with st.spinner("Veri indiriliyor..."):
                df = pd.read_csv(csv_url, encoding='utf-8-sig')
                df.columns = df.columns.str.strip()
                st.session_state.df = df
                st.session_state.active_data = df.head(500).to_string() # Limit
                st.session_state.active_url = current_url
                
        if "active_data" in st.session_state:
            df = st.session_state.df
            data_text = st.session_state.active_data
            
except Exception as e:
    st.error(f"Veri Yükleme Hatası: {e}")
    data_text = None

# --- 5. SOHBET ARAYÜZÜ ---
st.title("💼 Finansal Analiz Asistanı")
if df is not None:
    st.caption(f"✅ {selected_name} yüklü. {len(df)} satır veriden ilk 500 satır analiz ediliyor.")
    st.dataframe(df.head(200))

st.divider()

# Sohbet Geçmişi
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Soru Sorma
if prompt := st.chat_input("Veri hakkında sor (Örn: Toplam satış ne kadar?):"):
    if client is None: st.stop()
    
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        if not data_text:
            full_response = "Lütfen geçerli bir Google Sheets dosyası seçildiğinden emin olun."
        else:
            system_content = f"""
            Sen uzman bir finans asistanısın. Aşağıdaki tabloya göre soruları cevapla.
            Tablo:
            {data_text}
            """
            try:
                stream = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": system_content},
                        *st.session_state.messages
                    ],
                    stream=True,
                )
                for chunk in stream:
                    full_response += chunk.choices[0].delta.content or ""
                    message_placeholder.markdown(full_response + "▌")
            except Exception as e:
                full_response = f"Hata: {e}"
        
        message_placeholder.markdown(full_response)
    
    st.session_state.messages.append({"role": "assistant", "content": full_response})