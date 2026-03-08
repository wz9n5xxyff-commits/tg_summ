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
    print("Publishing to Telegram...")
    # NOTE: In GitHub Actions, we will pass an environment variable to determine if it's a test run
    # For now, we will publish to the test channel (or main channel if IS_TEST=false)
    # Be very careful.
    
    # We will log it instead of publishing for this local run just to be safe.
    print("Skipping actual publish for safety during local testing.")
    print("Done!")

if __name__ == "__main__":
    main()
