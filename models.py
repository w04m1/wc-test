"""
Pydantic models for HackerNews posts.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class HNPost(BaseModel):
    """
    Pydantic model representing a HackerNews post.

    Attributes collected for research purposes:
    - Identifiers: rank, post_id
    - Content: title, url, domain
    - Engagement: points, comments_count, author
    - Timing: posted_at, age_text
    - Metadata: page_number, scraped_at
    """

    # Post identifiers
    rank: int = Field(..., description="Position on the page (1-30 typically)")
    post_id: str = Field(..., description="HackerNews post ID")

    # Content
    title: str = Field(..., description="Post title")
    url: Optional[str] = Field(
        None, description="Link URL (can be None for Ask HN, etc.)"
    )
    domain: Optional[str] = Field(None, description="Domain of the link")

    # Engagement metrics
    points: int = Field(..., description="Number of upvotes")
    author: str = Field(..., description="Username of post author")
    comments_count: int = Field(..., description="Number of comments")

    # Timing information
    age_text: str = Field(..., description="Human-readable age (e.g., '2 hours ago')")
    posted_at: Optional[datetime] = Field(None, description="Estimated posting time")

    # Metadata
    page_number: int = Field(..., description="Which page this was scraped from")
    scraped_at: datetime = Field(
        default_factory=datetime.now, description="When this was scraped"
    )

    # Additional fields for research
    is_show_hn: bool = Field(
        default=False, description="Whether this is a 'Show HN' post"
    )
    is_ask_hn: bool = Field(
        default=False, description="Whether this is an 'Ask HN' post"
    )
    is_job: bool = Field(default=False, description="Whether this is a job posting")
    is_github_link: bool = Field(
        default=False, description="Whether URL points to GitHub"
    )
    is_twitter_link: bool = Field(
        default=False, description="Whether URL points to Twitter/X"
    )
    is_yc_company: bool = Field(
        default=False,
        description="Whether this mentions YC in title or is from YC company",
    )

    # GitHub star metrics (optional, populated if fetch_github_stars=True)
    github_repo_full_name: Optional[str] = Field(
        default=None, description="Full GitHub repo name (owner/repo)"
    )
    github_total_stars: Optional[int] = Field(
        default=None, description="Total number of stars fetched"
    )
    github_stars_before_hn: Optional[int] = Field(
        default=None, description="Stars given before HN post"
    )
    github_stars_after_hn: Optional[int] = Field(
        default=None, description="Stars given after HN post"
    )
    github_stars_fetched_at: Optional[datetime] = Field(
        default=None, description="When star data was fetched"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "rank": 1,
                "post_id": "45604700",
                "title": "Show HN: Inkeep (YC W23) – Agent Builder",
                "url": "https://github.com/inkeep/agents",
                "domain": "github.com/inkeep",
                "points": 72,
                "author": "engomez",
                "comments_count": 49,
                "age_text": "21 hours ago",
                "page_number": 2,
                "is_show_hn": True,
                "is_github_link": True,
                "is_yc_company": True,
            }
        }
