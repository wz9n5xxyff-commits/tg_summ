import os
import sys
from scraper import TelegramScraper
from ai_writer import generate_digest
from publisher import publish_to_telegram
from voice_export import build_alice_data, export_for_alice

CHANNEL = "yasnovolkova"


def run_digest(days=7, is_test=False, save_local=True):
    """Scrapes, generates and publishes the digest.

    Returns the Alice data (dict), or None when there were no posts.
    Raises RuntimeError if generation or publishing fails.
    """
    print("Starting TG Auto Digest...")

    # 1. Scrape
    posts = TelegramScraper(CHANNEL).get_recent_posts(days=days)
    if not posts:
        print("No posts found. Exiting.")
        return None

    print(f"Scraped {len(posts)} posts. Sending to AI...")

    # 2. Generate Digest
    digest_text = generate_digest(posts)
    if not digest_text:
        raise RuntimeError("Failed to generate digest.")

    print("Digest generated successfully:")
    print("-" * 40)
    print(digest_text)
    print("-" * 40)

    # 2.5 Voice-friendly copy for the Alice skill (non-fatal)
    alice_data = None
    try:
        alice_data = export_for_alice(digest_text, posts) if save_local else build_alice_data(digest_text, posts)
        print(f"Alice digest prepared: {len(alice_data['sections'])} sections.")
    except Exception as e:
        print(f"Warning: failed to export digest for Alice: {e}")

    # 3. Publish
    print(f"Publishing to Telegram... (Test mode: {is_test})")
    if not publish_to_telegram(digest_text, is_test=is_test):
        raise RuntimeError("Failed to publish.")

    print("Published successfully!")
    return alice_data


def main():
    days = int(os.environ.get("DIGEST_DAYS") or 7)
    is_test = os.environ.get("IS_TEST", "false").lower() == "true"
    try:
        alice_data = run_digest(days=days, is_test=is_test)
    except RuntimeError as e:
        print(e)
        sys.exit(1)

    # Optional: copy the voice version to Object Storage for the Alice skill
    if alice_data and os.environ.get("DIGEST_BUCKET") and os.environ.get("YC_SA_KEY"):
        from yc_storage import upload_digest
        try:
            upload_digest(alice_data)
        except Exception as e:
            print(f"Failed to upload digest to Object Storage: {e}")
            sys.exit(1)
    print("Done!")


if __name__ == "__main__":
    main()
