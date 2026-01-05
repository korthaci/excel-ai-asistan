import streamlit as st
import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv
import os
import json
import urllib.parse

# --- YAPILANDIRMA ---
load_dotenv()
st.set_page_config(page_title="AI Veri Asistanı", layout="wide")

@st.cache_resource
def get_client():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key: return None
    return OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")

client = get_client()

query_params = st.query_params
encoded_list = query_params.get("encoded_list", None)

# Ana sayfa yönlendirmesi için link (Senin gerçek URL'inle değiştirmeyi unutma)
ANA_SAYFA_URL = "https://vipotokiralama.com/excel_ai/"

# --- URL'DEN VERİ ALMA VE İŞLEME ---
if encoded_list:
    try:
        decoded_json = urllib.parse.unquote(encoded_list)
        received_links = json.loads(decoded_json)
        
        if isinstance(received_links, list) and len(received_links) > 0:
            st.header("📂 Dosya Seçimi")
            
            # Dosya seçimi için dictionary (İsim -> Link)
            file_options = {item['name']: item['url'] for item in received_links}
            
            selected_name = st.selectbox("Hangi dosyayı analiz etmek istiyorsunuz?", list(file_options.keys()))
            
            if selected_name:
                url_to_load = file_options[selected_name]
                sheet_id = url_to_load.split("/d/")[1].split("/")[0]
                csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
                
                # Veriyi İndir
                with st.spinner(f"{selected_name} yükleniyor..."):
                    df = pd.read_csv(csv_url, encoding='utf-8-sig')
                    df.columns = df.columns.str.strip()
                    st.session_state.df = df
                    
                    # --- AKILLI VERİ YÖNETİMİ ---
                    # Verinin tamamını metne çevirip uzunluğuna bakıyoruz.
                    raw_data_text = df.to_string()
                    data_len = len(raw_data_text)
                    
                    # Groq (Llama 3.3) genelde 100k+ token destekler ama 
                    # istikrarlı olması için ilk 20.000 karaktere kadar (yaklaşık 5k-10k satır) güvenle alabiliriz.
                    # Senin senaryonda max 200 satır olduğu için %100 tamamı buraya sığacaktır.
                    LIMIT_CHARS = 20000 
                    
                    if data_len <= LIMIT_CHARS:
                        st.session_state.active_data = raw_data_text
                        st.caption("💡 Tüm veri AI'a gönderildi.")
                    else:
                        st.warning(f"⚠️ Dosya çok büyük ({data_len} karakter). Analiz için özet gönderiliyor.")
                        # Çok büyükse sadece ilk 5000 karakterini alıyoruz ki hata vermesin
                        st.session_state.active_data = raw_data_text[:5000]
                
                st.success(f"✅ {selected_name} başarıyla yüklendi! ({len(df)} satır, {len(df.columns)} sütun)")
                
                # --- ÖZELLİK: DOSYA BAŞLIĞINI AI'A SOR ---
                with st.spinner("Dosya türü tespit ediliyor..."):
                    try:
                        intro_prompt = f"""Bu tabloya göre dosyanın ne hakkında olduğunu açıklayan kısa ve net bir başlık ver (Max 8 kelime):\n\n{st.session_state.active_data[:2000]}"""
                        intro_response = client.chat.completions.create(
                            model="llama-3.3-70b-versatile",
                            messages=[{"role": "user", "content": intro_prompt}]
                        )
                        ai_title = intro_response.choices[0].message.content
                        st.markdown(f"**🤖 AI Dosya Analizi:** {ai_title}")
                    except Exception as e:
                        pass # Hata olursa bu özelliği pas geçiyoruz

                st.divider()
                # Veri önizlemesi
                st.dataframe(df)

            # --- SOHBET KISMI ---
            st.divider()
            st.subheader("💬 Veri Analiz Asistanı")

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
                        # --- SİSTEM MESAJI (GENEL AMAÇLI) ---
                        system_content = f"""
Sen çok zeki, genel amaçlı bir veri analiz asistanısın.

Görevin:
Aşağıdaki tabloyu kullanıcıdan gelen sorulara göre analiz et. Tablonun ne hakkında olduğunu (Satış, Finans, Kayıt vb.) senin kanaatince belirle ve ona göre cevap ver.

Kurallar:
1. Kullanıcıya yardımcı ve samimi ol.
2. Veriyi kullanarak matematiksel hesaplar yapabilirsin (Toplam, Ortalama, Maksimum vb.).
3. Kullanıcının sorusu ile verideki sütunlar uyuşmuyorsa nazikçe yönlendirme yap.
4. Türkçe cevap ver.

Veri:
{st.session_state.active_data}
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
                    else:
                        full_response = "Lütfen önce bir dosya seçin."

                    message_placeholder.markdown(full_response)
                
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                
        else:
            st.error("Veri formatı hatalı veya boş.")

    except Exception as e:
        st.error(f"Veri işleme hatası: {e}")

else:
    st.warning("⚠️ Giriş Yapılmadı")
    st.write("Lütfen Ana Sayfa üzerinden giriş yaparak linklerinizi seçin.")
    if st.button("Ana Sayfaya Dön", use_container_width=True):
        st.link_button("🚀 Giriş Paneline Git", ANA_SAYFA_URL)
        
        
        
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
                st.dataframe(df.head(200))

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
