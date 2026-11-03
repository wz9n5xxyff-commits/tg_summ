import os
import requests
from dotenv import load_dotenv

load_dotenv()

TG_MAX_LENGTH = 4096  # Telegram limit for one message


def split_message(text, limit=TG_MAX_LENGTH):
    """Splits text into Telegram-sized parts on blank lines, then on lines.

    The digest keeps every HTML tag within one line, so splitting on line
    boundaries never breaks the markup.
    """
    if len(text) <= limit:
        return [text]

    parts, current = [], ""

    def flush():
        nonlocal current
        if current.strip():
            parts.append(current.strip())
        current = ""

    for block in text.split("\n\n"):
        candidate = f"{current}\n\n{block}" if current else block
        if len(candidate) <= limit:
            current = candidate
            continue
        flush()
        if len(block) <= limit:
            current = block
            continue
        # A single block is too long: fall back to line-by-line
        for line in block.split("\n"):
            candidate = f"{current}\n{line}" if current else line
            if len(candidate) <= limit:
                current = candidate
            else:
                flush()
                current = line[:limit]
    flush()
    return parts


def publish_to_telegram(text, is_test=True):
    """Publishes an HTML text to the Telegram channel (split if too long)."""
    bot_token = os.getenv("TG_BOT_TOKEN")
    if not bot_token:
        raise ValueError("TG_BOT_TOKEN not found in .env file.")

    channel_id = os.getenv("TG_TEST_CHANNEL_ID") if is_test else os.getenv("TG_CHANNEL_ID")
    if not channel_id:
        raise ValueError("TG_CHANNEL_ID or TG_TEST_CHANNEL_ID not found in .env file.")

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    parts = split_message(text)

    for idx, part in enumerate(parts, start=1):
        payload = {
            "chat_id": channel_id,
            "text": part,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        try:
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            print(f"❌ Failed to publish part {idx}/{len(parts)} to {channel_id}: {e.response.text}")
            return False
        except Exception as e:
            print(f"❌ Failed to publish part {idx}/{len(parts)} to {channel_id}: {e}")
            return False

    print(f"✅ Successfully published to {channel_id} ({len(parts)} message(s))")
    return True


if __name__ == "__main__":
    # Small test message
    test_msg = "<b>Привет!</b> Это тестовое сообщение от ИИ-бота."
    publish_to_telegram(test_msg)
