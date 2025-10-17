"""
GitHub Stars Module - Track star history for repositories posted on HackerNews.

This module provides functionality to fetch star timestamps from GitHub repositories
using the GitHub API. It handles pagination, rate limiting, and data storage.
"""

import time
import csv
from datetime import datetime
from typing import List, Optional, Dict, Tuple
from urllib.parse import urlparse
import requests
from pydantic import BaseModel, Field


class GitHubStar(BaseModel):
    """
    Represents a single star event on a GitHub repository.

    Attributes:
        repo_owner: Owner/organization of the repository
        repo_name: Name of the repository
        starred_at: Timestamp when the star was given
        user_login: GitHub username who starred the repo
    """

    repo_owner: str = Field(..., description="Repository owner/organization")
    repo_name: str = Field(..., description="Repository name")
    starred_at: datetime = Field(..., description="When the star was given")
    user_login: str = Field(..., description="GitHub user who starred")

    @property
    def repo_full_name(self) -> str:
        """Returns the full repository name in owner/repo format."""
        return f"{self.repo_owner}/{self.repo_name}"


class GitHubStarTracker:
    """
    Fetches and manages GitHub star history data.

    This class provides methods to fetch paginated star data from the GitHub API,
    handling rate limits and errors appropriately.
    """

    BASE_URL = "https://api.github.com"
    STARS_PER_PAGE = 100  # GitHub API max per page

    def __init__(self, delay: float = 1.0, github_token: Optional[str] = None):
        """
        Initialize the GitHub star tracker.

        Args:
            delay: Delay between API requests in seconds (default 1.0)
            github_token: Optional GitHub personal access token for higher rate limits
        """
        self.delay = delay
        self.headers = {"Accept": "application/vnd.github.v3.star+json"}

        if github_token:
            self.headers["Authorization"] = f"token {github_token}"

    def extract_repo_info(self, url: str) -> Optional[Tuple[str, str]]:
        """
        Extract owner and repo name from a GitHub URL.

        Args:
            url: GitHub URL (e.g., https://github.com/owner/repo)

        Returns:
            Tuple of (owner, repo) or None if not a valid GitHub repo URL

        Examples:
            >>> tracker = GitHubStarTracker()
            >>> tracker.extract_repo_info("https://github.com/inkeep/agents")
            ('inkeep', 'agents')
            >>> tracker.extract_repo_info("https://github.com/Kong/volcano-sdk")
            ('Kong', 'volcano-sdk')
        """
        if not url:
            return None

        try:
            parsed = urlparse(url)

            # Check if it's a GitHub URL
            if parsed.netloc not in ["github.com", "www.github.com"]:
                return None

            # Extract path parts
            path_parts = [p for p in parsed.path.split("/") if p]

            # Need at least owner/repo
            if len(path_parts) < 2:
                return None

            owner, repo = path_parts[0], path_parts[1]

            # Remove .git suffix if present
            if repo.endswith(".git"):
                repo = repo[:-4]

            return owner, repo

        except Exception as e:
            print(f"Error parsing URL {url}: {e}")
            return None

    def fetch_stars_page(
        self, owner: str, repo: str, page: int = 1
    ) -> Tuple[List[GitHubStar], bool]:
        """
        Fetch a single page of star data from GitHub API.

        Args:
            owner: Repository owner
            repo: Repository name
            page: Page number (1-indexed)

        Returns:
            Tuple of (list of GitHubStar objects, has_more_pages)

        Raises:
            requests.exceptions.RequestException: On API errors
        """
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/stargazers"
        params = {"per_page": self.STARS_PER_PAGE, "page": page}

        try:
            response = requests.get(
                url, headers=self.headers, params=params, timeout=30
            )

            # Handle rate limiting
            if response.status_code == 403:
                rate_limit_remaining = response.headers.get(
                    "X-RateLimit-Remaining", "0"
                )
                if rate_limit_remaining == "0":
                    reset_time = int(response.headers.get("X-RateLimit-Reset", 0))
                    wait_time = max(reset_time - time.time(), 0) + 5
                    print(f"Rate limit reached. Waiting {wait_time:.0f} seconds...")
                    time.sleep(wait_time)
                    return self.fetch_stars_page(owner, repo, page)  # Retry

            # Handle 422 (page out of range)
            if response.status_code == 422:
                return [], False

            # Handle 404 (repo not found)
            if response.status_code == 404:
                print(f"Repository {owner}/{repo} not found or has no stars")
                return [], False

            response.raise_for_status()

            data = response.json()

            # Convert to GitHubStar objects
            stars = []
            for item in data:
                try:
                    star = GitHubStar(
                        repo_owner=owner,
                        repo_name=repo,
                        starred_at=datetime.fromisoformat(
                            item["starred_at"].replace("Z", "+00:00")
                        ),
                        user_login=item["user"]["login"],
                    )
                    stars.append(star)
                except (KeyError, ValueError) as e:
                    print(f"Error parsing star data: {e}")
                    continue

            # Check if there are more pages
            has_more = len(data) == self.STARS_PER_PAGE

            return stars, has_more

        except requests.exceptions.RequestException as e:
            print(f"Error fetching stars for {owner}/{repo} (page {page}): {e}")
            raise

    def fetch_all_stars(
        self, owner: str, repo: str, max_pages: Optional[int] = None
    ) -> List[GitHubStar]:
        """
        Fetch all stars for a repository across all pages.

        Args:
            owner: Repository owner
            repo: Repository name
            max_pages: Optional limit on number of pages to fetch

        Returns:
            List of all GitHubStar objects
        """
        all_stars = []
        page = 1

        print(f"Fetching stars for {owner}/{repo}...")

        while True:
            if max_pages and page > max_pages:
                print(f"Reached max pages limit ({max_pages})")
                break

            try:
                stars, has_more = self.fetch_stars_page(owner, repo, page)

                if not stars:
                    break

                all_stars.extend(stars)
                print(
                    f"  Page {page}: fetched {len(stars)} stars (total: {len(all_stars)})"
                )

                if not has_more:
                    break

                page += 1

                # Delay between requests
                time.sleep(self.delay)

            except requests.exceptions.RequestException:
                print(f"Failed to fetch page {page}, stopping...")
                break

        print(f"Total stars fetched: {len(all_stars)}")
        return all_stars

    def fetch_stars_from_url(
        self, url: str, max_pages: Optional[int] = None
    ) -> List[GitHubStar]:
        """
        Fetch stars for a GitHub repository from its URL.

        Args:
            url: GitHub repository URL
            max_pages: Optional limit on number of pages to fetch

        Returns:
            List of GitHubStar objects or empty list if invalid URL
        """
        repo_info = self.extract_repo_info(url)

        if not repo_info:
            print(f"Could not extract repo info from URL: {url}")
            return []

        owner, repo = repo_info
        return self.fetch_all_stars(owner, repo, max_pages)

    def save_stars_to_csv(
        self, stars: List[GitHubStar], filename: str = "data/github_stars.csv"
    ):
        """
        Save star data to CSV file.

        Args:
            stars: List of GitHubStar objects
            filename: Output CSV filename
        """
        if not stars:
            print("No stars to save!")
            return

        fieldnames = [
            "repo_owner",
            "repo_name",
            "repo_full_name",
            "starred_at",
            "user_login",
        ]

        with open(filename, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for star in stars:
                writer.writerow(
                    {
                        "repo_owner": star.repo_owner,
                        "repo_name": star.repo_name,
                        "repo_full_name": star.repo_full_name,
                        "starred_at": star.starred_at.isoformat(),
                        "user_login": star.user_login,
                    }
                )

        print(f"Saved {len(stars)} stars to {filename}")

    def get_star_counts_by_date(self, stars: List[GitHubStar]) -> Dict[str, int]:
        """
        Aggregate star counts by date.

        Args:
            stars: List of GitHubStar objects

        Returns:
            Dictionary mapping date (YYYY-MM-DD) to star count
        """
        counts = {}

        for star in stars:
            date_key = star.starred_at.date().isoformat()
            counts[date_key] = counts.get(date_key, 0) + 1

        return counts


def main():
    """Example usage of the GitHubStarTracker."""

    # Initialize tracker
    tracker = GitHubStarTracker(delay=1.0)

    # Example: Fetch stars for a repository
    url = "https://github.com/inkeep/agents"

    # Fetch all stars (or limit pages for testing)
    stars = tracker.fetch_stars_from_url(url, max_pages=5)

    if stars:
        # Save to CSV
        tracker.save_stars_to_csv(stars)

        # Show some statistics
        counts = tracker.get_star_counts_by_date(stars)
        print("\nStar counts by date:")
        for date, count in sorted(counts.items())[:10]:
            print(f"  {date}: {count} stars")


if __name__ == "__main__":
    main()
