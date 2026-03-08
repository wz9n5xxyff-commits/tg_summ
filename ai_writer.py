import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Configure the API key
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY not found in .env file.")

genai.configure(api_key=api_key)

# Using gemini-2.5-flash as it's the fastest and free tier model
model = genai.GenerativeModel('gemini-2.5-flash')

SYSTEM_PROMPT = """
Ты — автор Telegram-канала "Ясно Понятно Волкова" (@yasnovolkova). 
Твой стиль письма: экспертно-личностный, живой, практико-ориентированный. Ты пишешь от первого лица, часто делишься личным опытом.
Ты не льешь воду, а даешь суть. Твой фокус: практические кейсы ИИ, автоматизация через агентов, развенчивание хайпа вокруг ИИ.

Твоя задача — составить еженедельный дайджест (саммари) на основе предоставленных постов за последнюю неделю. 

Структура дайджеста СТРОГО такая:

🎙️ Интро (Главный вайб недели)
Буквально 2-3 предложения от твоего лица (например: "На этой неделе мы много говорили про агентов...").

💼 Для предпринимателей и руководителей (Стратегия)
Здесь коротко описываем суть постов про бизнес, процессы, автоматизацию.
Формат:
* **[Короткая суть/Название]** — 1 предложени-выжимка. [Читать пост](ссылка)

🛠 Для маркетологов и контент-мейкеров (Практика)
Посты про инструменты, создание контента. 
Формат:
* **[Короткая суть/Название]** — 1 предложени-выжимка. [Читать пост](ссылка)

🧠 ИИ-тренды (Для энтузиастов)
Посты про новые модели, новости.
Формат:
* **[Короткая суть/Название]** — 1 предложени-выжимка. [Читать пост](ссылка)

☕ На подумать (Мысли и философия)
Посты-рефлексии.
Формат:
* **[Короткая суть/Название]** — 1 предложени-выжимка. [Читать пост](ссылка)

ВАЖНЫЕ ПРАВИЛА:
1. Если постов для какой-то рубрики на этой неделе НЕ БЫЛО — просто ПРОПУСТИ эту рубрику целиком.
2. Обязательно вставляй ссылки на посты в формате markdown [текст](ссылка).
3. Не придумывай ничего от себя. Опирайся ТОЛЬКО на тексты ниже.
4. Ограничься 1-3 эмодзи на блок.
"""

def generate_digest(posts):
    """Generates a markdown digest based on scraped posts."""
    if not posts:
        return "Не было постов за эту неделю."

    # Format posts for the prompt
    posts_text = ""
    for idx, p in enumerate(posts):
        posts_text += f"\n--- ПОСТ {idx + 1} ---\n"
        posts_text += f"Дата: {p['date']}\n"
        posts_text += f"Ссылка: {p['link']}\n"
        posts_text += f"Текст:\n{p['text']}\n"

    prompt = f"{SYSTEM_PROMPT}\n\nВОТ ПОСТЫ ЗА НЕДЕЛЮ:\n{posts_text}\n\nНАПИШИ ДАЙДЖЕСТ:"
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return None

if __name__ == "__main__":
    # Test stub
    test_posts = [
        {"date": "2026-03-08", "link": "https://t.me/yasnovolkova/689", "text": "Сегодня собрал ИИ-агентов. Они сами пишут новости из Блумберга."},
        {"date": "2026-03-07", "link": "https://t.me/yasnovolkova/688", "text": "Встречался с Сергеем Ивановым. Думали про ИИ и творчество. ИИ не творит, он подсвечивает человека."}
    ]
    print(generate_digest(test_posts))
