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

# Ana sayfa yönlendirmesi için link
ANA_SAYFA_URL = "https://vipotokiralama.com/excel_ai/" 

# --- URL'DEN VERİ ALMA VE İŞLEME ---
if encoded_list:
    try:
        decoded_json = urllib.parse.unquote(encoded_list)
        received_links = json.loads(decoded_json)
        
        if isinstance(received_links, list) and len(received_links) > 0:
            st.header("📂 Dosya Seçimi")
            
            # HTML'den gelen objeleri dictionary'ye çevir (İsim -> URL)
            file_options = {item['name']: item['url'] for item in received_links}
            
            selected_name = st.selectbox("Hangi dosyayı analiz etmek istiyorsunuz?", list(file_options.keys()))
            
            if selected_name:
                url_to_load = file_options[selected_name]
                
                # Link ID'sini al
                try:
                    if "/d/" not in url_to_load:
                        st.error("Link formatı hatalı.")
                        st.stop()
                        
                    sheet_id = url_to_load.split("/d/")[1].split("/")[0]
                    csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
                    
                    # Veriyi İndir
                    with st.spinner(f"{selected_name} yükleniyor..."):
                        df = pd.read_csv(csv_url, encoding='utf-8-sig')
                        df.columns = df.columns.str.strip()
                        st.session_state.df = df
                        
                        # --- AKILLI VERİ YÖNETİMİ ---
                        raw_data_text = df.to_string()
                        data_len = len(raw_data_text)
                        LIMIT_CHARS = 20000
                        
                        if data_len <= LIMIT_CHARS:
                            st.session_state.active_data = raw_data_text
                            st.caption("💡 Tüm veri AI'a gönderildi.")
                        else:
                            st.warning(f"⚠️ Dosya çok büyük ({data_len} karakter). Analiz için özet gönderiliyor.")
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
                    # Veri önizlemesi (Tümü)
                    st.dataframe(df)

                    # --- SOHBET KISMI ---
                    st.subheader("💬 Veri Analiz Asistanı")

                    # --- SESLİ KOMUT (SADECE MOBİL) ---
                    user_agent = st.context.headers.get('User-Agent', '').lower()
                    is_mobile = any(device in user_agent for device in ['android', 'iphone', 'ipad', 'mobil'])

                    if is_mobile:
                        st.components.v1.html("""
                            <style>
                                .mic-button {
                                    position: relative;
                                    display: inline-block;
                                    margin-left: 15px;
                                    margin-top: -10px;
                                    vertical-align: middle;
                                    cursor: pointer;
                                    font-size: 24px;
                                    background: transparent;
                                    border: none;
                                }
                            </style>
                            <button id="mobileMicBtn" class="mic-button">🎙️</button>
                            
                            <script>
                                document.getElementById('mobileMicBtn').addEventListener('click', function() {
                                    if (window.hasOwnProperty('webkitSpeechRecognition')) {
                                        var recognition = new webkitSpeechRecognition();
                                        recognition.continuous = false;
                                        recognition.interimResults = false;
                                        recognition.lang = "tr-TR";
                                        recognition.start();
                                
                                        // Görsel geri bildirim
                                        this.style.opacity = "0.5";
                                        this.innerHTML = "🔴";
                                
                                        recognition.onresult = function(e) {
                                            recognition.stop();
                                            var text = e.results[0][0].transcript;
                                            
                                            // İkonu eski haline getir
                                            var btn = document.getElementById('mobileMicBtn');
                                            btn.style.opacity = "1";
                                            btn.innerHTML = "🎙️";
                                
                                            // Yazıyı input'a ekle
                                            var chatInput = document.querySelector('[data-testid="stChatInputTextArea"]');
                                            if(chatInput) {
                                                chatInput.value = text;
                                                var event = new KeyboardEvent('keydown', {bubbles: true, cancelable: true, keyCode: 13});
                                                chatInput.dispatchEvent(event);
                                            } else {
                                                alert("Söylenen: " + text + "\\n(Lütfen yazıyı sohbet kutusuna yapıştırın)");
                                            }
                                        };
                                
                                        recognition.onerror = function(e) {
                                            recognition.stop();
                                            var btn = document.getElementById('mobileMicBtn');
                                            btn.style.opacity = "1";
                                            btn.innerHTML = "🎙️";
                                            alert("Dinleme hatası: " + e.error);
                                        };
                                    } else {
                                        alert("Tarayıcınız sesli aramayı desteklemiyor.");
                                    }
                                });
                            </script>
                        """)

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
Aşağıdaki tabloyu kullanıcıdan gelen sorulara göre analiz et.
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
                
                except Exception as e:
                    st.error(f"Link işleme hatası: {e}")
                
        else:
            st.error("Veri formatı hatalı veya boş (Liste bulunamadı).")

    except Exception as e:
        st.error(f"Veri işleme hatası: {e}")

else:
    # --- GİRİŞ YAPILMADIĞI DURUM ---
    st.warning("⚠️ Giriş Yapılmadı")
    st.write("Lütfen Ana Sayfa üzerinden giriş yaparak linklerinizi seçin.")
    if st.button("Ana Sayfaya Dön", use_container_width=True):
        st.link_button("🚀 Giriş Paneline Git", ANA_SAYFA_URL)
