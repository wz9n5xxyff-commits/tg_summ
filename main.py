import sys
from scraper import TelegramScraper
from ai_writer import generate_digest
from publisher import publish_to_telegram
from voice_export import export_for_alice

def main():
    print("Starting TG Auto Digest...")
    
    # 1. Scrape
    scraper = TelegramScraper("yasnovolkova")
    posts = scraper.get_recent_posts(days=7)
    
    if not posts:
        print("No posts found. Exiting.")
        return

    print(f"Scraped {len(posts)} posts. Sending to AI...")
    
    # 2. Generate Digest
    digest_text = generate_digest(posts)
    if not digest_text:
        print("Failed to generate digest. Exiting.")
        sys.exit(1)
        
    print("Digest generated successfully:")
    print("-" * 40)
    print(digest_text)
    print("-" * 40)

    # 2.5 Save a voice-friendly copy for the Alice skill (non-fatal)
    try:
        alice_data = export_for_alice(digest_text, posts)
        print(f"Alice digest saved: {len(alice_data['sections'])} sections.")
    except Exception as e:
        print(f"Warning: failed to export digest for Alice: {e}")

    # 3. Publish
    import os
    is_test_run = os.environ.get("IS_TEST", "false").lower() == "true"
    print(f"Publishing to Telegram... (Test mode: {is_test_run})")
    
    success = publish_to_telegram(digest_text, is_test=is_test_run)
    if success:
        print("Published successfully!")
    else:
        print("Failed to publish.")
        sys.exit(1)
        
    print("Done!")

if __name__ == "__main__":
    main()
