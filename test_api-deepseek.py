from openai import OpenAI

client = OpenAI(
    api_key = os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

print("DeepSeek'e bağlanılıyor...")

try:
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "Sen yardımcı bir asistansın."},
            {"role": "user", "content": "Merhaba! Bağlantımız var mı?"}
        ]
    )

    cevap = response.choices[0].message.content
    print(f"AI Cevabı: {cevap}")

except Exception as e:
    print(f"Bir hata oluştu: {e}")