"""
Main script for scraping HackerNews posts using the API.
"""

from hackernews import HackerNews


def main():
    """
    Main function to scrape HackerNews posts using Algolia API.
    This properly fetches 6 months of historical data.
    """
    print("=" * 70)
    print("HackerNews Scraper - Using Algolia API for 6 Months of Data")
    print("=" * 70)

    # Initialize HackerNews client
    client = HackerNews(delay=0.5)

    # Scrape 6 months of data (180 days)
    days = 180

    print(f"\nFetching posts from last {days} days ({days / 30:.0f} months)...")
    print("This may take a few minutes...")
    print("(For testing, you can add max_posts parameter to limit the number)\n")

    # Fetch posts - uncomment max_posts for testing
    # posts = client.fetch_posts(days=days, max_posts=1000, method="api")
    posts = client.fetch_posts(days=days, method="api")

    # Save to CSV
    if posts:
        filename = "data/hackernews_6months.csv"
        client.save_to_csv(posts, filename)

        print("\n" + "=" * 70)
        print(f"✓ Successfully fetched {len(posts)} posts")
        print(f"✓ Saved to: {filename}")
        print("=" * 70)

        # Print statistics
        print("\nDataset Statistics:")
        print(f"  Total posts: {len(posts)}")
        print(f"  Show HN posts: {sum(p.is_show_hn for p in posts)}")
        print(f"  Ask HN posts: {sum(p.is_ask_hn for p in posts)}")
        print(f"  GitHub links: {sum(p.is_github_link for p in posts)}")
        print(f"  Twitter links: {sum(p.is_twitter_link for p in posts)}")
        print(f"  YC companies: {sum(p.is_yc_company for p in posts)}")
        print(f"  Job posts: {sum(p.is_job for p in posts)}")

        # Show average engagement
        avg_points = sum(p.points for p in posts) / len(posts) if posts else 0
        avg_comments = sum(p.comments_count for p in posts) / len(posts) if posts else 0
        print(f"\n  Average points: {avg_points:.1f}")
        print(f"  Average comments: {avg_comments:.1f}")

        # Date range
        valid_dates = [p.posted_at for p in posts if p.posted_at]
        if valid_dates:
            print(
                f"\n  Date range: {min(valid_dates).date()} to {max(valid_dates).date()}"
            )

        print("\n" + "=" * 70)
        print("Data collection complete! Ready for analysis.")
        print("=" * 70)
    else:
        print("No posts were fetched!")


if __name__ == "__main__":
    main()
