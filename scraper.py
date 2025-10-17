"""
HackerNews scraper to collect posts for analysis.
"""

import time
import csv
from datetime import datetime, timedelta
from typing import List, Optional
import requests
from bs4 import BeautifulSoup
from models import HNPost


class HackerNewsScraper:
    """
    Scraper for HackerNews front page posts.

    This scraper collects data from HackerNews over multiple pages,
    parsing post details for research and analysis.
    """

    BASE_URL = "https://news.ycombinator.com"

    def __init__(self, delay: float = 1.0):
        """
        Initialize the scraper.

        Args:
            delay: Delay between requests in seconds (be respectful!)
        """
        self.delay = delay
        self.headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "accept-language": "en-US,en;q=0.9",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
            "referer": f"{self.BASE_URL}/",
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def fetch_page(self, page_number: int = 1) -> Optional[str]:
        """
        Fetch a single page from HackerNews.

        Args:
            page_number: Page number to fetch (1-indexed)

        Returns:
            HTML content as string, or None if request fails
        """
        try:
            if page_number == 1:
                url = self.BASE_URL
            else:
                url = f"{self.BASE_URL}/?p={page_number}"

            print(f"Fetching page {page_number}: {url}")
            response = self.session.get(url)
            response.raise_for_status()

            # Be respectful - add delay between requests
            time.sleep(self.delay)

            return response.text
        except requests.RequestException as e:
            print(f"Error fetching page {page_number}: {e}")
            return None

    def parse_age_to_datetime(self, age_text: str) -> Optional[datetime]:
        """
        Convert HackerNews age text to approximate datetime.

        Args:
            age_text: Text like "2 hours ago", "3 days ago"

        Returns:
            Estimated datetime of post
        """
        try:
            now = datetime.now()
            parts = age_text.lower().split()

            if len(parts) < 2:
                return None

            value = int(parts[0])
            unit = parts[1]

            if "minute" in unit:
                return now - timedelta(minutes=value)
            elif "hour" in unit:
                return now - timedelta(hours=value)
            elif "day" in unit:
                return now - timedelta(days=value)
            elif "month" in unit:
                return now - timedelta(days=value * 30)  # Approximate
            elif "year" in unit:
                return now - timedelta(days=value * 365)  # Approximate

            return None
        except (ValueError, IndexError):
            return None

    def parse_page(self, html: str, page_number: int) -> List[HNPost]:
        """
        Parse HTML content to extract post information.

        Args:
            html: HTML content of the page
            page_number: Page number being parsed

        Returns:
            List of HNPost objects
        """
        soup = BeautifulSoup(html, "html.parser")
        posts = []

        # Find all post rows (class "athing")
        post_rows = soup.find_all("tr", class_="athing")

        for post_row in post_rows:
            try:
                # Extract post ID
                post_id_raw = post_row.get("id", "")
                post_id = str(post_id_raw) if post_id_raw else ""

                # Extract rank
                rank_span = post_row.find("span", class_="rank")
                rank = int(rank_span.text.strip(".")) if rank_span else 0

                # Extract title and URL
                titleline = post_row.find("span", class_="titleline")
                if not titleline:
                    continue

                title_link = titleline.find("a")
                if not title_link:
                    continue

                title = title_link.text.strip()
                url_raw = title_link.get("href", "")
                url = str(url_raw) if url_raw else ""

                # Handle relative URLs
                if url and not url.startswith("http"):
                    url = f"{self.BASE_URL}/{url}"

                # Extract domain
                domain = None
                sitebit = titleline.find("span", class_="sitebit")
                if sitebit:
                    sitestr = sitebit.find("span", class_="sitestr")
                    if sitestr:
                        domain = sitestr.text.strip()

                # Get the metadata row (next sibling)
                meta_row = post_row.find_next_sibling("tr")
                if not meta_row:
                    continue

                subtext = meta_row.find("td", class_="subtext")
                if not subtext:
                    # This is a job posting - handle differently
                    posts.append(
                        HNPost(
                            rank=rank,
                            post_id=post_id,
                            title=title,
                            url=url if url else None,
                            domain=domain,
                            points=0,
                            author="",
                            comments_count=0,
                            age_text="",
                            posted_at=None,
                            page_number=page_number,
                            is_job=True,
                        )
                    )
                    continue

                # Extract points
                score_span = subtext.find("span", class_="score")
                points = 0
                if score_span:
                    points_text = score_span.text.strip()
                    points = int(points_text.split()[0]) if points_text else 0

                # Extract author
                author_link = subtext.find("a", class_="hnuser")
                author = author_link.text.strip() if author_link else ""

                # Extract age
                age_span = subtext.find("span", class_="age")
                age_text = ""
                posted_at = None
                if age_span:
                    age_link = age_span.find("a")
                    if age_link:
                        age_text = age_link.text.strip()
                        posted_at = self.parse_age_to_datetime(age_text)

                # Extract comment count
                comments_count = 0
                comment_links = subtext.find_all("a")
                for link in comment_links:
                    link_text = link.text.strip()
                    if "comment" in link_text.lower():
                        # Parse "49 comments" or "discuss"
                        if link_text.lower() == "discuss":
                            comments_count = 0
                        else:
                            try:
                                comments_count = int(link_text.split()[0])
                            except (ValueError, IndexError):
                                comments_count = 0
                        break

                # Analyze title and URL for research flags
                title_lower = title.lower()
                is_show_hn = "show hn" in title_lower
                is_ask_hn = "ask hn" in title_lower
                is_yc_company = "yc" in title_lower or "(yc" in title.lower()

                # Check URL patterns
                url_lower = url.lower() if url else ""
                is_github_link = "github.com" in url_lower
                is_twitter_link = any(
                    domain_part in url_lower for domain_part in ["twitter.com", "x.com"]
                )

                # Create post object
                post = HNPost(
                    rank=rank,
                    post_id=post_id,
                    title=title,
                    url=url if url else None,
                    domain=domain,
                    points=points,
                    author=author,
                    comments_count=comments_count,
                    age_text=age_text,
                    posted_at=posted_at,
                    page_number=page_number,
                    is_show_hn=is_show_hn,
                    is_ask_hn=is_ask_hn,
                    is_job=False,
                    is_github_link=is_github_link,
                    is_twitter_link=is_twitter_link,
                    is_yc_company=is_yc_company,
                )

                posts.append(post)

            except Exception as e:
                print(f"Error parsing post: {e}")
                continue

        return posts

    def scrape_pages(self, num_pages: int) -> List[HNPost]:
        """
        Scrape multiple pages of HackerNews.

        Args:
            num_pages: Number of pages to scrape

        Returns:
            List of all scraped posts
        """
        all_posts = []

        for page_num in range(1, num_pages + 1):
            html = self.fetch_page(page_num)
            if html:
                posts = self.parse_page(html, page_num)
                all_posts.extend(posts)
                print(f"Scraped {len(posts)} posts from page {page_num}")
            else:
                print(f"Failed to scrape page {page_num}")

        return all_posts

    def save_to_csv(
        self, posts: List[HNPost], filename: str = "data/hackernews_posts.csv"
    ):
        """
        Save scraped posts to CSV file.

        Args:
            posts: List of HNPost objects
            filename: Output CSV filename
        """
        if not posts:
            print("No posts to save!")
            return

        # Get field names from the model
        fieldnames = list(posts[0].model_dump().keys())

        with open(filename, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for post in posts:
                # Convert datetime objects to ISO format strings
                post_dict = post.model_dump()
                for key, value in post_dict.items():
                    if isinstance(value, datetime):
                        post_dict[key] = value.isoformat() if value else ""

                writer.writerow(post_dict)

        print(f"Saved {len(posts)} posts to {filename}")

    @staticmethod
    def estimate_pages_for_timeframe(days: int) -> int:
        """
        Estimate how many pages to scrape for a given timeframe.

        Assumptions:
        - HackerNews has ~30 posts per page
        - Front page refreshes roughly every few hours
        - To get 6 months of data, we need historical pages

        Args:
            days: Number of days to cover

        Returns:
            Estimated number of pages
        """
        # For 6 months (~180 days), we'll need a lot of pages
        # HackerNews shows about 30 posts per page
        # Let's estimate conservatively - this is for recent data only
        # For true historical data, you'd need the HN API or archive

        if days <= 1:
            return 10  # Last ~day
        elif days <= 7:
            return 50  # Last week
        elif days <= 30:
            return 200  # Last month
        else:
            # Note: Scraping HN front page won't get you 6 months of data
            # You need to use the HN API (algolia) for that
            print("WARNING: Scraping front page only gets recent posts.")
            print("For 6 months of data, use HackerNews API (Algolia HN Search)")
            return 500  # This won't actually give 6 months, but will get a lot of data
