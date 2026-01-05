import streamlit as st
import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv
import os
import json
import urllib.parse
import time

load_dotenv()
st.set_page_config(page_title="Finans Asistanı", layout="wide")

@st.cache_resource
def get_client():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key: return None
    return OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")

client = get_client()

# --- URL'DEN DİZİ (ARRAY) ALMA ---
query_params = st.query_params
encoded_list = query_params.get("encoded_list", None)

# --- ANA SAYFA URL'İ (KENDİ SUNUCUNDAKİ HTML DOSYASI) ---
# BURAYI KENDİ REAL URL'İNLE DEĞİŞTİR
ANA_SAYFA_URL = "https://vipotokiralama.com/excel_ai/" 

if encoded_list:
    try:
        decoded_json = urllib.parse.unquote(encoded_list)
        received_links = json.loads(decoded_json)
        
        if isinstance(received_links, list) and len(received_links) > 0:
            # --- DÖKÜMAN SEÇİMİ ---
            st.header("📂 Aktif Dosya Seçimi")
            
            # Kullanıcıya gelen linklerden birini seçtirelim
            # Linkler uzun olduğu için sadece numara veya kısa isim gösterelim
            file_options = {}
            for i, url in enumerate(received_links):
                file_options[f"{i+1}. Dosya"] = url
            
            selected_file = st.selectbox("Hangi dosyayı analiz etmek istiyorsunuz?", list(file_options.keys()))
            
            if selected_file:
                url_to_load = file_options[selected_file]
                sheet_id = url_to_load.split("/d/")[1].split("/")[0]
                csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
                
                with st.spinner("Veri yükleniyor..."):
                    df = pd.read_csv(csv_url, encoding='utf-8-sig')
                    df.columns = df.columns.str.strip()
                    st.session_state.df = df
                    st.session_state.active_data = df.head(50).to_string() # Limitli
                
                st.success(f"Veri başarıyla yüklendi! ({len(df)} satır)")
                st.dataframe(df.head(10))

            # --- SOHBET KISMI ---
            st.divider()
            st.subheader("💬 AI Analiz Asistanı")

            if "messages" not in st.session_state:
                st.session_state.messages = []

            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

            if prompt := st.chat_input("Veri hakkında bir soru sor..."):
                if client is None: st.stop()
                
                st.session_state.messages.append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)

                with st.chat_message("assistant"):
                    message_placeholder = st.empty()
                    full_response = ""
                    
                    if st.session_state.get("active_data"):
                        system_content = f"""Sen finans asistanısın. Veri: {st.session_state.active_data}"""
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
                    else:
                        full_response = "Lütfen önce bir dosya seçin."

                    message_placeholder.markdown(full_response)
                
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                
        else:
            st.error("Veri formatı hatalı veya boş.")

    except Exception as e:
        st.error(f"Veri işleme hatası: {e}")

else:
    # --- YÖNLENDİRME EKRANI ---
    st.warning("⚠️ Giriş Yapılmadı")
    st.write("Lütfen Ana Sayfa üzerinden giriş yaparak linklerinizi seçin.")
    
    # Butona basınca ana sayfaya git
    if st.button("Ana Sayfaya Dön", use_container_width=True):
        st.link_button("🚀 Giriş Paneline Git", ANA_SAYFA_URL)
