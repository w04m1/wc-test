"""
HackerNews API scraper using Algolia HN Search API.
This is the proper way to get 6 months of historical data.
"""

import time
import csv
from datetime import datetime, timedelta
from typing import List, Optional
import requests
from models import HNPost


class HNAPIClient:
    """
    Fetch HackerNews data using the Algolia HN Search API.
    This is the recommended way to get historical data.
    """

    BASE_URL = "http://hn.algolia.com/api/v1/search_by_date"

    def __init__(self, delay: float = 0.5):
        """
        Initialize the API client.

        Args:
            delay: Delay between API requests in seconds
        """
        self.delay = delay
        self.session = requests.Session()

    def fetch_posts_in_timeframe(
        self, days: int = 180, max_posts: Optional[int] = None
    ) -> List[HNPost]:
        """
        Fetch all posts from the last N days using the API.

        Args:
            days: Number of days to look back
            max_posts: Maximum number of posts to fetch (None = unlimited)

        Returns:
            List of HNPost objects
        """
        cutoff_timestamp = int((datetime.now() - timedelta(days=days)).timestamp())
        all_posts = []
        page = 0

        print(f"Fetching posts from last {days} days...")
        print(f"Cutoff date: {datetime.fromtimestamp(cutoff_timestamp)}")

        while True:
            # Adjust hits per page if we're close to max_posts
            hits_per_page = 1000
            if max_posts:
                remaining = max_posts - len(all_posts)
                if remaining <= 0:
                    print(f"Reached max_posts limit: {max_posts}")
                    break
                hits_per_page = min(1000, remaining)

            params = {
                "tags": "story",
                "numericFilters": f"created_at_i>{cutoff_timestamp}",
                "hitsPerPage": hits_per_page,
                "page": page,
            }

            try:
                response = self.session.get(self.BASE_URL, params=params)
                response.raise_for_status()
                data = response.json()

                hits = data.get("hits", [])
                if not hits:
                    print(f"No more posts found on page {page}")
                    break

                # Convert API response to HNPost objects
                for hit in hits:
                    try:
                        post = self._convert_api_hit_to_post(hit, page)
                        if post:
                            all_posts.append(post)
                    except Exception as e:
                        print(f"Error parsing post {hit.get('objectID')}: {e}")
                        continue

                page += 1
                print(f"Fetched page {page}, total posts: {len(all_posts)}")

                time.sleep(self.delay)

            except requests.RequestException as e:
                print(f"API request error on page {page}: {e}")
                break

        return all_posts

    def _convert_api_hit_to_post(self, hit: dict, page: int) -> Optional[HNPost]:
        """
        Convert Algolia API hit to HNPost model.

        Args:
            hit: API response hit object
            page: Page number

        Returns:
            HNPost object or None
        """
        # Extract basic fields
        post_id = str(hit.get("objectID", ""))
        title = hit.get("title", "")
        url = hit.get("url")

        # Skip if no title
        if not title:
            return None

        # Extract domain
        domain = None
        if url:
            try:
                from urllib.parse import urlparse

                parsed = urlparse(url)
                domain = parsed.netloc
            except Exception:
                pass

        # Extract engagement metrics
        points = hit.get("points", 0) or 0
        author = hit.get("author", "")
        comments_count = hit.get("num_comments", 0) or 0

        # Extract timestamp
        created_at_i = hit.get("created_at_i")
        posted_at = None
        age_text = ""
        if created_at_i:
            posted_at = datetime.fromtimestamp(created_at_i)
            # Calculate age
            age_delta = datetime.now() - posted_at
            if age_delta.days > 0:
                age_text = f"{age_delta.days} days ago"
            else:
                hours = age_delta.seconds // 3600
                if hours > 0:
                    age_text = f"{hours} hours ago"
                else:
                    minutes = age_delta.seconds // 60
                    age_text = f"{minutes} minutes ago"

        # Analyze title and URL
        title_lower = title.lower()
        is_show_hn = "show hn" in title_lower
        is_ask_hn = "ask hn" in title_lower
        is_yc_company = "yc" in title_lower or "(yc" in title.lower()

        url_lower = url.lower() if url else ""
        is_github_link = "github.com" in url_lower
        is_twitter_link = any(d in url_lower for d in ["twitter.com", "x.com"])

        # Check if job posting
        story_type = hit.get("_tags", [])
        is_job = "job" in story_type if isinstance(story_type, list) else False

        return HNPost(
            rank=0,  # Not applicable for API results
            post_id=post_id,
            title=title,
            url=url,
            domain=domain,
            points=points,
            author=author,
            comments_count=comments_count,
            age_text=age_text,
            posted_at=posted_at,
            page_number=page,
            is_show_hn=is_show_hn,
            is_ask_hn=is_ask_hn,
            is_job=is_job,
            is_github_link=is_github_link,
            is_twitter_link=is_twitter_link,
            is_yc_company=is_yc_company,
        )

    def save_to_csv(self, posts: List[HNPost], filename: str = "data/hn_api_posts.csv"):
        """
        Save posts to CSV file.

        Args:
            posts: List of HNPost objects
            filename: Output CSV filename
        """
        if not posts:
            print("No posts to save!")
            return

        fieldnames = list(posts[0].model_dump().keys())

        with open(filename, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for post in posts:
                post_dict = post.model_dump()
                for key, value in post_dict.items():
                    if isinstance(value, datetime):
                        post_dict[key] = value.isoformat() if value else ""

                writer.writerow(post_dict)

        print(f"Saved {len(posts)} posts to {filename}")


if __name__ == "__main__":
    # Test the API client
    client = HNAPIClient(delay=0.5)

    # Fetch last 7 days for testing
    posts = client.fetch_posts_in_timeframe(days=7, max_posts=100)

    if posts:
        print(f"\nFetched {len(posts)} posts")
        print(
            f"Date range: {min(p.posted_at for p in posts if p.posted_at)} to {max(p.posted_at for p in posts if p.posted_at)}"
        )

        # Save to CSV
        client.save_to_csv(posts, "data/test_api_posts.csv")
    else:
        print("No posts fetched!")
