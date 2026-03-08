import sys
from scraper import TelegramScraper
from ai_writer import generate_digest
from publisher import publish_to_telegram

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
