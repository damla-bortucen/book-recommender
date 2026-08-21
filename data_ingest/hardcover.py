"""
Pull the Hardcover catalogue into Postgres. 
Safe to re-run: upserts (update + insert) on hardcover_id.
"""

import os
import time

import httpx
import psycopg
from dotenv import load_dotenv
from datetime import date

load_dotenv()


API_URL = "https://api.hardcover.app/v1/graphql"
MIN_USERS = 25       # only books with at least this many readers
TOKEN = os.environ["HARDCOVER_TOKEN"]
MIN_TAG_COUNT = 1
PAGE_SIZE = 1000     # Hardcover's maximum


QUERY = """
query Books($limit: Int!, $offset: Int!, $minUsers: Int!) {
  books(
    limit: $limit
    offset: $offset
    where: {
        users_count: {_gte: $minUsers}, 
        description: {_is_null: false}}
        # skip unreleased books — a recommendation you can't go and read is noise.
        # release_date beats release_year: it also catches titles due later this year.
        _or: [
            {release_date: {_lte: $today}}
            {release_date: {_is_null: true}}
        ]
    }
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


UPSERT = """
INSERT INTO books (
    hardcover_id, slug, title, authors, description, cover_url,
    isbn13, release_year, pages, rating, ratings_count, users_count,
    genres, moods, content_warnings
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (hardcover_id) DO UPDATE SET
    slug = EXCLUDED.slug,
    title = EXCLUDED.title,
    authors = EXCLUDED.authors,
    description = EXCLUDED.description,
    cover_url = EXCLUDED.cover_url,
    isbn13 = EXCLUDED.isbn13,
    release_year = EXCLUDED.release_year,
    pages = EXCLUDED.pages,
    rating = EXCLUDED.rating,
    ratings_count = EXCLUDED.ratings_count,
    users_count = EXCLUDED.users_count,
    genres = EXCLUDED.genres,
    moods = EXCLUDED.moods,
    content_warnings = EXCLUDED.content_warnings,
    updated_at = now(),
    -- a changed description invalidates the stored vector
    embedding = CASE
        WHEN books.description IS DISTINCT FROM EXCLUDED.description THEN NULL
        ELSE books.embedding
    END
"""


def positive(value: int | None) -> int | None:
    """
    None for missing-value placeholders — 0 pages means unknown, not zero.
    """

    return value if value and value > 0 else None


def fetch(limit: int, offset: int = 0) -> list[dict]:
    response = httpx.post(
        API_URL,
        json={"query": QUERY, 
              "variables": {"limit": limit, "offset": offset, "minUsers": MIN_USERS, "today": date.today().isoformat()},
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
        book.get("release_year"), positive(book.get("pages")), book.get("rating"),
        book.get("ratings_count"), book["users_count"],
        tags(cached, "Genre"), tags(cached, "Mood"), tags(cached, "Content Warning"),
    )


def main() -> None:
    total = 0
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        offset = 0 # skip first X, as you move through the catalogue
        while True:
            books = fetch(limit=PAGE_SIZE, offset=offset)
            if not books:
                break
            with conn.cursor() as cur:
                cur.executemany(UPSERT, [to_row(b) for b in books])
            conn.commit()
            total += len(books)
            print(f"{total:,} books upserted (offset {offset:,})")
            offset += PAGE_SIZE
            time.sleep(1)   # stay under 60 requests/minute
    print(f"done: {total:,} books")


if __name__ == "__main__":
    main()