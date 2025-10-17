"""
HackerNews Module - Unified interface for scraping HackerNews data.

This module provides both API-based and web scraping methods for collecting
HackerNews posts. The API method is recommended for historical data.
"""

import time
import csv
from datetime import datetime, timedelta
from typing import List, Optional
import requests
from bs4 import BeautifulSoup
from models import HNPost
from github_stars import GitHubStarTracker


class HackerNews:
    """
    Main interface for interacting with HackerNews data.

    This class provides a unified interface for both API-based and web scraping
    methods of collecting HackerNews posts.
    """

    def __init__(self, delay: float = 0.5, github_token: Optional[str] = None):
        """
        Initialize the HackerNews client.

        Args:
            delay: Delay between requests in seconds
            github_token: Optional GitHub token for fetching star data
        """
        self.api_client = HNAPIClient(delay=delay)
        self.web_scraper = HNWebScraper(delay=max(1.0, delay))  # Min 1s for web
        self.github_tracker = (
            GitHubStarTracker(delay=max(1.0, delay), github_token=github_token)
            if github_token
            else None
        )

    def fetch_posts(
        self,
        days: int = 7,
        max_posts: Optional[int] = None,
        method: str = "api",
        fetch_github_stars: bool = False,
        max_star_pages: Optional[int] = None,
    ) -> List[HNPost]:
        """
        Fetch HackerNews posts using specified method.

        Args:
            days: Number of days to look back
            max_posts: Maximum number of posts to fetch
            method: "api" (recommended) or "web"
            fetch_github_stars: If True, fetch GitHub star data for repos
            max_star_pages: Max pages of stars to fetch per repo (100 stars/page)

        Returns:
            List of HNPost objects
        """
        if method == "api":
            posts = self.api_client.fetch_posts_in_timeframe(days, max_posts)
        elif method == "web":
            # Estimate pages needed for timeframe
            pages = self._estimate_pages(days)
            posts = self.web_scraper.scrape_pages(pages)
        else:
            raise ValueError(f"Unknown method: {method}. Use 'api' or 'web'")

        # Fetch GitHub star data if requested
        if fetch_github_stars and posts:
            posts = self._enrich_with_github_stars(posts, max_star_pages)

        return posts

    def save_to_csv(self, posts: List[HNPost], filename: str = "data/hackernews.csv"):
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

    def _enrich_with_github_stars(
        self, posts: List[HNPost], max_star_pages: Optional[int] = None
    ) -> List[HNPost]:
        """
        Enrich GitHub posts with star data.

        Args:
            posts: List of HNPost objects
            max_star_pages: Max pages of stars to fetch per repo

        Returns:
            List of HNPost objects with GitHub star data populated
        """
        if not self.github_tracker:
            print(
                "⚠️  GitHub token not provided, initializing tracker without authentication"
            )
            self.github_tracker = GitHubStarTracker(delay=1.0)

        github_posts = [p for p in posts if p.is_github_link and p.url]

        if not github_posts:
            print("No GitHub posts found to enrich")
            return posts

        print(f"\n⭐ Enriching {len(github_posts)} GitHub posts with star data...")
        print(f"   Max pages per repo: {max_star_pages or 'unlimited'}")

        # Track which repos we've already processed (to avoid duplicates)
        processed_repos = {}

        for i, post in enumerate(github_posts, 1):
            print(f"\n[{i}/{len(github_posts)}] {post.title[:60]}...")

            if not post.url:
                continue

            repo_info = self.github_tracker.extract_repo_info(post.url)
            if not repo_info:
                print("  ⚠️  Could not extract repo info")
                continue

            owner, repo = repo_info
            repo_full_name = f"{owner}/{repo}"

            # Check if we already processed this repo
            if repo_full_name in processed_repos:
                print(f"  ⏭️  Already processed {repo_full_name}, reusing data")
                star_data = processed_repos[repo_full_name]
                post.github_repo_full_name = star_data["repo_full_name"]
                post.github_total_stars = star_data["total_stars"]
                post.github_stars_before_hn = star_data["stars_before_hn"]
                post.github_stars_after_hn = star_data["stars_after_hn"]
                post.github_stars_fetched_at = star_data["fetched_at"]
                continue

            try:
                # Fetch stars
                stars = self.github_tracker.fetch_all_stars(
                    owner, repo, max_pages=max_star_pages
                )

                if not stars:
                    print("  ⚠️  No stars found")
                    continue

                # Calculate stars before/after HN post
                total_stars = len(stars)
                stars_before = 0
                stars_after = 0

                if post.posted_at:
                    stars_before = len(
                        [s for s in stars if s.starred_at < post.posted_at]
                    )
                    stars_after = len(
                        [s for s in stars if s.starred_at >= post.posted_at]
                    )

                # Update post with star data
                post.github_repo_full_name = repo_full_name
                post.github_total_stars = total_stars
                post.github_stars_before_hn = stars_before
                post.github_stars_after_hn = stars_after
                post.github_stars_fetched_at = datetime.now()

                print(
                    f"  ✓ {total_stars} stars (before: {stars_before}, after: {stars_after})"
                )

                # Cache the result
                processed_repos[repo_full_name] = {
                    "repo_full_name": repo_full_name,
                    "total_stars": total_stars,
                    "stars_before_hn": stars_before,
                    "stars_after_hn": stars_after,
                    "fetched_at": post.github_stars_fetched_at,
                }

            except KeyboardInterrupt:
                print(
                    "\n⚠️  Interrupted by user, returning posts with partial star data"
                )
                return posts
            except Exception as e:
                print(f"  ✗ Error: {e}")
                continue

        print(f"\n✓ Enriched {len(processed_repos)} unique repos with star data")
        return posts

    def _estimate_pages(self, days: int) -> int:
        """Estimate pages needed for web scraping."""
        if days <= 1:
            return 10
        elif days <= 7:
            return 50
        elif days <= 30:
            return 200
        else:
            print("WARNING: Web scraping limited to recent posts.")
            print("For historical data (>30 days), use method='api'")
            return 500


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


class HNWebScraper:
    """
    Scraper for HackerNews front page posts.

    This scraper collects data from HackerNews over multiple pages,
    parsing post details for research and analysis.
    Note: Limited to recent posts visible on the front page.
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
        Parse HTML page to extract post data.

        Args:
            html: HTML content of the page
            page_number: Page number being parsed

        Returns:
            List of parsed HNPost objects
        """
        soup = BeautifulSoup(html, "html.parser")
        posts = []

        # Find all post rows
        post_rows = soup.find_all("tr", class_="athing")

        for post_row in post_rows:
            try:
                # Extract rank and post ID
                rank_span = post_row.find("span", class_="rank")
                rank = int(rank_span.text.strip().rstrip(".")) if rank_span else 0
                post_id = str(post_row.get("id", ""))

                # Extract title and URL
                title_cell = post_row.find("span", class_="titleline")
                if not title_cell:
                    continue

                title_link = title_cell.find("a")
                if not title_link:
                    continue

                title = title_link.text.strip()
                url = str(title_link.get("href", ""))

                # Extract domain
                domain = None
                domain_span = title_cell.find("span", class_="sitestr")
                if domain_span:
                    domain = domain_span.text.strip()

                # Get subtext row (next sibling)
                subtext = post_row.find_next_sibling("tr")
                if not subtext:
                    continue

                subtext_td = subtext.find("td", class_="subtext")
                if not subtext_td:
                    continue

                # Extract points
                points = 0
                score_span = subtext_td.find("span", class_="score")
                if score_span:
                    try:
                        points = int(score_span.text.strip().split()[0])
                    except (ValueError, IndexError):
                        points = 0

                # Extract author
                author = ""
                author_link = subtext_td.find("a", class_="hnuser")
                if author_link:
                    author = author_link.text.strip()

                # Extract age
                age_text = ""
                posted_at = None
                age_link = subtext_td.find("span", class_="age")
                if age_link:
                    age_link = age_link.find("a")
                    if age_link:
                        age_text = age_link.text.strip()
                        posted_at = self.parse_age_to_datetime(age_text)

                # Extract comment count
                comments_count = 0
                comment_links = subtext.find_all("a")
                for link in comment_links:
                    link_text = link.text.strip()
                    if "comment" in link_text.lower():
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
                url_lower = url.lower()
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


# Convenience functions for quick usage
def fetch_posts(days: int = 7, max_posts: Optional[int] = None) -> List[HNPost]:
    """
    Quick function to fetch HackerNews posts using API.

    Args:
        days: Number of days to look back
        max_posts: Maximum number of posts to fetch

    Returns:
        List of HNPost objects
    """
    client = HackerNews()
    return client.fetch_posts(days=days, max_posts=max_posts, method="api")


def save_posts(posts: List[HNPost], filename: str = "data/hackernews.csv"):
    """
    Quick function to save posts to CSV.

    Args:
        posts: List of HNPost objects
        filename: Output CSV filename
    """
    client = HackerNews()
    client.save_to_csv(posts, filename)


if __name__ == "__main__":
    # Test the unified interface
    print("Testing HackerNews Module")
    print("=" * 70)

    hn = HackerNews(delay=0.3)

    # Fetch 1 day of posts for testing
    posts = hn.fetch_posts(days=1, max_posts=50, method="api")

    if posts:
        print(f"\n✓ Fetched {len(posts)} posts")
        print(f"✓ Show HN: {sum(p.is_show_hn for p in posts)}")
        print(f"✓ Ask HN: {sum(p.is_ask_hn for p in posts)}")

        # Save to CSV
        hn.save_to_csv(posts, "data/test_hackernews.csv")
    else:
        print("Failed to fetch posts!")
