import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
import logging

logging.basicConfig(level=logging.INFO)

MAX_PAGES = 10  # safety cap: ~20 posts per page


class TelegramScraper:
    def __init__(self, channel_name):
        self.channel_name = channel_name.replace('@', '')
        self.base_url = f"https://t.me/s/{self.channel_name}"

    def _fetch_page(self, before=None):
        params = {"before": before} if before else None
        response = requests.get(self.base_url, params=params, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        return soup.find_all('div', class_='tgme_widget_message')

    @staticmethod
    def _message_id(msg):
        data_post = msg.get('data-post', '')
        try:
            return int(data_post.rsplit('/', 1)[-1])
        except ValueError:
            return None

    @staticmethod
    def _parse_message(msg):
        """Returns (post_time_utc_naive, text, link) or None."""
        time_tag = msg.find('time', class_='time')
        if not time_tag or not time_tag.has_attr('datetime'):
            return None
        post_time = datetime.fromisoformat(time_tag['datetime'].replace('Z', '+00:00'))
        if post_time.tzinfo:
            post_time = post_time.astimezone(timezone.utc).replace(tzinfo=None)

        text_div = msg.find('div', class_='tgme_widget_message_text')
        post_text = text_div.get_text(separator='\n', strip=True) if text_div else ""

        link = ""
        date_wrap = msg.find('a', class_='tgme_widget_message_date')
        if date_wrap and date_wrap.has_attr('href'):
            link = date_wrap['href']
        return post_time, post_text, link

    def get_recent_posts(self, days=7):
        """Scrapes posts from the last N days, loading older pages as needed."""
        logging.info(f"Scraping posts from {self.base_url} for the last {days} days...")

        cutoff_date = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
        posts, seen_links = [], set()
        before = None

        for page in range(MAX_PAGES):
            try:
                messages = self._fetch_page(before)
            except Exception as e:
                logging.error(f"Failed to fetch {self.base_url} (before={before}): {e}")
                break
            if not messages:
                break

            oldest_time = None
            for msg in messages:
                parsed = self._parse_message(msg)
                if not parsed:
                    continue
                post_time, post_text, link = parsed
                oldest_time = post_time if oldest_time is None else min(oldest_time, post_time)

                if post_time < cutoff_date or link in seen_links:
                    continue
                # Skip empty or very short posts (like just an image or "Hi")
                if len(post_text) < 20:
                    continue

                seen_links.add(link)
                posts.append({'date': post_time, 'text': post_text, 'link': link})

            ids = [i for i in (self._message_id(m) for m in messages) if i]
            # Stop once the page already reaches past the cutoff
            if oldest_time is None or oldest_time < cutoff_date or not ids:
                break
            next_before = min(ids)
            if before is not None and next_before >= before:
                break
            before = next_before
            logging.info(f"Page {page + 1} done, loading older posts (before={before})...")

        posts.sort(key=lambda p: p['date'])
        logging.info(f"Found {len(posts)} relevant posts.")
        return posts


if __name__ == "__main__":
    scraper = TelegramScraper("yasnovolkova")
    posts = scraper.get_recent_posts()
    for p in posts:
        print(f"[{p['date']}] {p['link']}\n{p['text'][:100]}...\n")
