import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin
import logging

logging.basicConfig(level=logging.INFO)

class TelegramScraper:
    def __init__(self, channel_name):
        self.channel_name = channel_name.replace('@', '')
        self.base_url = f"https://t.me/s/{self.channel_name}"

    def get_recent_posts(self, days=7):
        """Scrapes posts from the last N days."""
        logging.info(f"Scraping posts from {self.base_url} for the last {days} days...")
        
        try:
            response = requests.get(self.base_url)
            response.raise_for_status()
        except Exception as e:
            logging.error(f"Failed to fetch {self.base_url}: {e}")
            return []

        soup = BeautifulSoup(response.content, 'html.parser')
        messages = soup.find_all('div', class_='tgme_widget_message')
        
        cutoff_date = datetime.now() - timedelta(days=days)
        posts = []

        for msg in messages:
            # Extract time
            time_tag = msg.find('time', class_='time')
            if not time_tag or not time_tag.has_attr('datetime'):
                continue
                
            post_time = datetime.fromisoformat(time_tag['datetime'].replace('Z', '+00:00')).replace(tzinfo=None)
            
            if post_time < cutoff_date:
                continue

            # Extract text
            text_div = msg.find('div', class_='tgme_widget_message_text')
            post_text = text_div.get_text(separator='\n', strip=True) if text_div else ""
            
            # Skip empty or very short posts (like just an image or "Hi")
            if len(post_text) < 20: 
                continue

            # Extract link
            link = ""
            date_wrap = msg.find('a', class_='tgme_widget_message_date')
            if date_wrap and date_wrap.has_attr('href'):
                link = date_wrap['href']

            posts.append({
                'date': post_time,
                'text': post_text,
                'link': link
            })
            
        logging.info(f"Found {len(posts)} relevant posts.")
        return posts

if __name__ == "__main__":
    scraper = TelegramScraper("yasnovolkova")
    posts = scraper.get_recent_posts()
    for p in posts:
        print(f"[{p['date']}] {p['link']}\n{p['text'][:100]}...\n")
