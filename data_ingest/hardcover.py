"""
Pull the Hardcover catalogue into Postgres. 
Safe to re-run: upserts (update + insert) on hardcover_id.
"""

import os
import time

import httpx
import psycopg
from dotenv import load_dotenv

load_dotenv()


API_URL = "https://api.hardcover.app/v1/graphql"
MIN_USERS = 25       # only books with at least this many readers
TOKEN = os.environ["HARDCOVER_TOKEN"]
MIN_TAG_COUNT = 2    # ignore tags only one person applied (tags = categories)

QUERY = """
query Books($limit: Int!, $offset: Int!, $minUsers: Int!) {
  books(
    limit: $limit
    offset: $offset
    where: {users_count: {_gte: $minUsers}, description: {_is_null: false}}
    order_by: [{users_count: desc}, {id: asc}]
  ) {
    id slug title description
    users_count rating ratings_count release_year pages
    image { url }
    default_physical_edition { isbn_13 }
    contributions { author { name } }
    cached_tags
  }
}
"""
# slug: the book's URL segment on hardcover.app, e.g. hardcover.app/books/1984


def fetch(limit: int, offset: int = 0) -> list[dict]:
    response = httpx.post(
        API_URL,
        json={"query": QUERY, 
              "variables": {"limit": limit, "offset": offset, "minUsers": MIN_USERS},
        },
        headers={"Authorization": TOKEN},
        timeout=60.0,
    )
    response.raise_for_status()
    payload = response.json()
    if "errors" in payload:              # GraphQL reports errors inside a 200
        raise RuntimeError(payload["errors"])
    return payload["data"]["books"]


def tags(cached: dict | None, category: str) -> list[str]:
    """
    One category out of cached_tags, most-applied first, weak tags dropped.
    """
    items = (cached or {}).get(category) or []
    kept = [i for i in items if i.get("count", 0) >= MIN_TAG_COUNT]
    kept.sort(key=lambda i: i["count"], reverse=True)
    return [i["tag"] for i in kept]


def to_row(book: dict) -> tuple:
    """
    Flatten a book from the API into a tuple = a row.
    Nested objects are optional so they are defaulted before read. 
    """

    # any of these nested objects can come back null
    edition = book.get("default_physical_edition") or {}
    image = book.get("image") or {}
    authors = [c["author"]["name"] for c in book.get("contributions") or [] if c.get("author")]
    cached = book.get("cached_tags")

    return (
        book["id"], book.get("slug"), book["title"],
        authors, book["description"], image.get("url"), edition.get("isbn_13"),
        book.get("release_year"), book.get("pages"), book.get("rating"),
        book.get("ratings_count"), book["users_count"],
        tags(cached, "Genre"), tags(cached, "Mood"), tags(cached, "Content Warning"),
    )


if __name__ == "__main__":
    row = to_row(fetch(1)[0])
    for value in row:
        print(repr(value)[:100]) # only the first 100 chars so that it can be read in terminal