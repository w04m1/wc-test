"""
HackerNews-GitHub Integration Module

This module integrates HackerNews post data with GitHub star tracking.
It processes HN posts, identifies GitHub links, and fetches star history
for analysis of the "Hacker News effect" on GitHub repositories.
"""

import csv
from datetime import datetime
from typing import List, Optional, Dict, Any

from models import HNPost
from github_stars import GitHubStarTracker, GitHubStar


class HNGitHubAnalyzer:
    """
    Analyzes the relationship between HackerNews posts and GitHub stars.

    This class processes HN posts, fetches star data for linked GitHub repos,
    and prepares data for statistical analysis of the HN effect.
    """

    def __init__(self, github_token: Optional[str] = None, delay: float = 1.0):
        """
        Initialize the analyzer.

        Args:
            github_token: Optional GitHub personal access token
            delay: Delay between GitHub API requests in seconds
        """
        self.star_tracker = GitHubStarTracker(delay=delay, github_token=github_token)

    def load_posts_from_csv(self, filename: str) -> List[HNPost]:
        """
        Load HackerNews posts from CSV file.

        Args:
            filename: Path to CSV file with HN posts

        Returns:
            List of HNPost objects
        """
        posts = []

        with open(filename, "r", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)

            for row in reader:
                # Convert string values to appropriate types
                post_data = {
                    "rank": int(row["rank"]),
                    "post_id": row["post_id"],
                    "title": row["title"],
                    "url": row["url"] if row["url"] else None,
                    "domain": row["domain"] if row["domain"] else None,
                    "points": int(row["points"]),
                    "author": row["author"],
                    "comments_count": int(row["comments_count"]),
                    "age_text": row["age_text"],
                    "posted_at": (
                        datetime.fromisoformat(row["posted_at"])
                        if row["posted_at"]
                        else None
                    ),
                    "page_number": int(row["page_number"]),
                    "scraped_at": datetime.fromisoformat(row["scraped_at"]),
                    "is_show_hn": row["is_show_hn"].lower() == "true",
                    "is_ask_hn": row["is_ask_hn"].lower() == "true",
                    "is_job": row["is_job"].lower() == "true",
                    "is_github_link": row["is_github_link"].lower() == "true",
                    "is_twitter_link": row["is_twitter_link"].lower() == "true",
                    "is_yc_company": row["is_yc_company"].lower() == "true",
                }

                posts.append(HNPost(**post_data))

        print(f"Loaded {len(posts)} posts from {filename}")
        return posts

    def filter_github_posts(self, posts: List[HNPost]) -> List[HNPost]:
        """
        Filter posts that link to GitHub repositories.

        Args:
            posts: List of HNPost objects

        Returns:
            List of posts with GitHub links
        """
        github_posts = [p for p in posts if p.is_github_link and p.url]
        print(f"Found {len(github_posts)} posts with GitHub links")
        return github_posts

    def fetch_stars_for_posts(
        self, posts: List[HNPost], max_pages_per_repo: Optional[int] = None
    ) -> Dict[str, List[GitHubStar]]:
        """
        Fetch star data for all GitHub repos in the posts.

        Args:
            posts: List of HNPost objects with GitHub links
            max_pages_per_repo: Optional limit on pages to fetch per repo

        Returns:
            Dictionary mapping repo_full_name to list of GitHubStar objects
        """
        results = {}

        for i, post in enumerate(posts, 1):
            print(f"\n[{i}/{len(posts)}] Processing: {post.title}")
            print(f"  URL: {post.url}")
            print(f"  Posted: {post.posted_at}")
            print(f"  Points: {post.points}, Comments: {post.comments_count}")

            if not post.url:
                print("  ⚠️  No URL in post")
                continue

            repo_info = self.star_tracker.extract_repo_info(post.url)
            if not repo_info:
                print("  ⚠️  Could not extract repo info")
                continue

            owner, repo = repo_info
            repo_full_name = f"{owner}/{repo}"

            # Skip if already fetched
            if repo_full_name in results:
                print(f"  ⏭️  Already fetched {repo_full_name}")
                continue

            try:
                stars = self.star_tracker.fetch_all_stars(
                    owner, repo, max_pages=max_pages_per_repo
                )

                if stars:
                    results[repo_full_name] = stars
                    print(f"  ✓ Fetched {len(stars)} stars")
                else:
                    print("  ⚠️  No stars found")

            except Exception as e:
                print(f"  ✗ Error: {e}")

        return results

    def save_stars_with_metadata(
        self,
        stars_by_repo: Dict[str, List[GitHubStar]],
        posts: List[HNPost],
        filename: str = "data/github_stars_with_hn_metadata.csv",
    ):
        """
        Save star data with HN post metadata for analysis.

        Args:
            stars_by_repo: Dictionary mapping repo to star list
            posts: List of HNPost objects
            filename: Output CSV filename
        """
        # Create a mapping of repo to HN post
        repo_to_post = {}
        for post in posts:
            if post.url:
                repo_info = self.star_tracker.extract_repo_info(post.url)
                if repo_info:
                    owner, repo = repo_info
                    repo_full_name = f"{owner}/{repo}"
                    repo_to_post[repo_full_name] = post

        # Prepare data for CSV
        rows: List[Dict[str, Any]] = []
        for repo_full_name, stars in stars_by_repo.items():
            post = repo_to_post.get(repo_full_name)

            for star in stars:
                row: Dict[str, Any] = {
                    "repo_owner": star.repo_owner,
                    "repo_name": star.repo_name,
                    "repo_full_name": repo_full_name,
                    "starred_at": star.starred_at.isoformat(),
                    "user_login": star.user_login,
                }

                # Add HN post metadata if available
                if post:
                    row["hn_post_id"] = post.post_id
                    row["hn_title"] = post.title
                    row["hn_posted_at"] = (
                        post.posted_at.isoformat() if post.posted_at else ""
                    )
                    row["hn_points"] = post.points
                    row["hn_comments"] = post.comments_count
                    row["hn_rank"] = post.rank
                    row["is_show_hn"] = post.is_show_hn
                else:
                    row["hn_post_id"] = ""
                    row["hn_title"] = ""
                    row["hn_posted_at"] = ""
                    row["hn_points"] = 0
                    row["hn_comments"] = 0
                    row["hn_rank"] = 0
                    row["is_show_hn"] = False

                rows.append(row)

        if not rows:
            print("No data to save!")
            return

        # Write to CSV
        fieldnames = list(rows[0].keys())

        with open(filename, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        print(f"\n✓ Saved {len(rows)} star records to {filename}")

    def generate_analysis_summary(
        self, stars_by_repo: Dict[str, List[GitHubStar]], posts: List[HNPost]
    ) -> Dict:
        """
        Generate a summary of the collected data for analysis.

        Args:
            stars_by_repo: Dictionary mapping repo to star list
            posts: List of HNPost objects

        Returns:
            Dictionary with summary statistics
        """
        summary = {
            "total_posts": len(posts),
            "total_repos": len(stars_by_repo),
            "total_stars": sum(len(stars) for stars in stars_by_repo.values()),
            "repos": [],
        }

        # Create a mapping of repo to HN post
        repo_to_post = {}
        for post in posts:
            if post.url:
                repo_info = self.star_tracker.extract_repo_info(post.url)
                if repo_info:
                    owner, repo = repo_info
                    repo_full_name = f"{owner}/{repo}"
                    repo_to_post[repo_full_name] = post

        for repo_full_name, stars in stars_by_repo.items():
            post = repo_to_post.get(repo_full_name)

            repo_summary = {
                "repo": repo_full_name,
                "total_stars": len(stars),
                "first_star": min(s.starred_at for s in stars).isoformat()
                if stars
                else None,
                "last_star": max(s.starred_at for s in stars).isoformat()
                if stars
                else None,
            }

            if post and post.posted_at:
                # Calculate stars before and after HN post
                stars_before = [s for s in stars if s.starred_at < post.posted_at]
                stars_after = [s for s in stars if s.starred_at >= post.posted_at]

                repo_summary.update(
                    {
                        "hn_posted_at": post.posted_at.isoformat(),
                        "hn_points": post.points,
                        "hn_comments": post.comments_count,
                        "stars_before_hn": len(stars_before),
                        "stars_after_hn": len(stars_after),
                    }
                )

            summary["repos"].append(repo_summary)

        return summary


def main():
    """Example usage of the HNGitHubAnalyzer."""

    # Initialize analyzer
    # For higher rate limits, provide a GitHub token:
    # analyzer = HNGitHubAnalyzer(github_token="your_token_here")
    analyzer = HNGitHubAnalyzer(delay=1.0)

    # Load HackerNews posts
    posts = analyzer.load_posts_from_csv("data/hackernews_7days.csv")

    # Filter for GitHub posts
    github_posts = analyzer.filter_github_posts(posts)

    # For testing, limit to first N posts
    test_posts = github_posts[:5]
    print(f"\n📊 Processing first {len(test_posts)} GitHub posts for testing...")

    # Fetch star data (limit pages for testing)
    stars_by_repo = analyzer.fetch_stars_for_posts(
        test_posts,
        max_pages_per_repo=10,  # Remove or increase for full data
    )

    # Save results
    if stars_by_repo:
        analyzer.save_stars_with_metadata(
            stars_by_repo, github_posts, "data/github_stars_with_hn_metadata.csv"
        )

        # Generate and print summary
        summary = analyzer.generate_analysis_summary(stars_by_repo, github_posts)
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Total HN posts with GitHub links: {summary['total_posts']}")
        print(f"Total repos processed: {summary['total_repos']}")
        print(f"Total stars collected: {summary['total_stars']}")
        print("\nTop repos by star count:")
        for repo in sorted(
            summary["repos"], key=lambda r: r["total_stars"], reverse=True
        )[:5]:
            print(f"  {repo['repo']}: {repo['total_stars']} stars")


if __name__ == "__main__":
    main()
