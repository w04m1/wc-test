"""
Main script for scraping HackerNews posts WITH GitHub star data.

This script demonstrates the integrated workflow where GitHub star data
is automatically fetched for repos posted on HackerNews.
"""

from hackernews import HackerNews
import argparse


def main():
    """
    Main function to scrape HackerNews posts with optional GitHub star data.
    """
    parser = argparse.ArgumentParser(
        description="Scrape HackerNews posts with optional GitHub star data"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to look back (default: 7)",
    )
    parser.add_argument(
        "--max-posts",
        type=int,
        default=None,
        help="Maximum number of posts to fetch (default: all)",
    )
    parser.add_argument(
        "--fetch-stars",
        action="store_true",
        help="Fetch GitHub star data for repos",
    )
    parser.add_argument(
        "--max-star-pages",
        type=int,
        default=None,
        help="Max pages of stars per repo (100 stars/page, default: all)",
    )
    parser.add_argument(
        "--github-token",
        type=str,
        default=None,
        help="GitHub personal access token (recommended for --fetch-stars)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output CSV filename (default: auto-generated)",
    )

    args = parser.parse_args()

    print("=" * 70)
    print("HackerNews Scraper with GitHub Star Integration")
    print("=" * 70)
    print(f"Timeframe: Last {args.days} days")
    print(f"Max posts: {args.max_posts or 'unlimited'}")
    print(f"Fetch GitHub stars: {args.fetch_stars}")
    if args.fetch_stars:
        print(f"Max star pages per repo: {args.max_star_pages or 'unlimited'}")
        print(
            f"GitHub token: {'Yes (5000 req/hr)' if args.github_token else 'No (60 req/hr)'}"
        )
    print("=" * 70)

    # Initialize HackerNews client
    client = HackerNews(delay=0.5, github_token=args.github_token)

    print(f"\n📥 Fetching HackerNews posts from last {args.days} days...")

    if args.fetch_stars:
        print("⚠️  This will also fetch GitHub star data (may take longer)")

    # Fetch posts
    posts = client.fetch_posts(
        days=args.days,
        max_posts=args.max_posts,
        method="api",
        fetch_github_stars=args.fetch_stars,
        max_star_pages=args.max_star_pages,
    )

    # Save to CSV
    if posts:
        # Generate filename
        if args.output:
            filename = args.output
        else:
            if args.fetch_stars:
                filename = f"data/hackernews_{args.days}days_with_stars.csv"
            else:
                filename = f"data/hackernews_{args.days}days.csv"

        client.save_to_csv(posts, filename)

        print("\n" + "=" * 70)
        print("RESULTS")
        print("=" * 70)
        print(f"✓ Successfully fetched {len(posts)} posts")
        print(f"✓ Saved to: {filename}")
        print("=" * 70)

        # Print statistics
        print("\n📊 Dataset Statistics:")
        print(f"  Total posts:        {len(posts)}")
        print(f"  Show HN posts:      {sum(p.is_show_hn for p in posts)}")
        print(f"  Ask HN posts:       {sum(p.is_ask_hn for p in posts)}")
        print(f"  GitHub links:       {sum(p.is_github_link for p in posts)}")
        print(f"  Job posts:          {sum(p.is_job for p in posts)}")

        if args.fetch_stars:
            posts_with_stars = [p for p in posts if p.github_total_stars is not None]
            print("\n⭐ GitHub Star Statistics:")
            print(f"  Repos with stars:   {len(posts_with_stars)}")

            if posts_with_stars:
                total_stars = sum(
                    p.github_total_stars
                    for p in posts_with_stars
                    if p.github_total_stars
                )
                print(f"  Total stars:        {total_stars}")
                print(
                    f"  Avg stars per repo: {total_stars / len(posts_with_stars):.1f}"
                )

                # Top repos by stars
                print("\n  Top 5 repos by stars:")
                sorted_posts = sorted(
                    posts_with_stars,
                    key=lambda p: p.github_total_stars or 0,
                    reverse=True,
                )[:5]

                for post in sorted_posts:
                    stars_info = f"{post.github_total_stars} stars"
                    if post.github_stars_before_hn is not None:
                        stars_info += f" (before: {post.github_stars_before_hn}, after: {post.github_stars_after_hn})"
                    print(f"    {post.github_repo_full_name:40} {stars_info}")

        print("\n" + "=" * 70)

        if args.fetch_stars:
            print("✅ Next steps:")
            print("   1. Analyze the data in Jupyter notebook")
            print("   2. Compare star rates before/after HN posts")
            print("   3. Run statistical tests for significance")
        else:
            print("💡 Tip: Use --fetch-stars to automatically gather GitHub star data")
            print(
                "   Example: python main_with_stars.py --days 7 --fetch-stars --github-token YOUR_TOKEN"
            )

        print("=" * 70)
    else:
        print("\n❌ No posts fetched!")


if __name__ == "__main__":
    main()
