import os
import requests
from dotenv import load_dotenv

load_dotenv()

def publish_to_telegram(text, is_test=True):
    """Publishes a markdown text to the Telegram channel."""
    bot_token = os.getenv("TG_BOT_TOKEN")
    if not bot_token:
        raise ValueError("TG_BOT_TOKEN not found in .env file.")

    channel_id = os.getenv("TG_TEST_CHANNEL_ID") if is_test else os.getenv("TG_CHANNEL_ID")
    if not channel_id:
        raise ValueError("TG_CHANNEL_ID or TG_TEST_CHANNEL_ID not found in .env file.")

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    payload = {
        "chat_id": channel_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print(f"✅ Successfully published to {channel_id}")
        return True
    except requests.exceptions.HTTPError as e:
        print(f"❌ Failed to publish to {channel_id}: {e.response.text}")
        return False
    except Exception as e:
        print(f"❌ Failed to publish to {channel_id}: {e}")
        return False

if __name__ == "__main__":
    # Small test message
    test_msg = "*Привет!* Это тестовое сообщение от ИИ-бота."
    publish_to_telegram(test_msg)
