"""Embed book descriptions into pgvector. Safe to re-run: only fills empty embeddings."""

import os

import psycopg
from dotenv import load_dotenv
from openai import OpenAI
from pgvector.psycopg import register_vector

load_dotenv()

MODEL = "text-embedding-3-small"
DIMENSIONS = 512      # reduced from the model's native 1536
BATCH_SIZE = 200      # texts per API call
MAX_CHARS = 20_000    # defensive cap, the model's limit is ~8k tokens

SELECT_PENDING = """
SELECT hardcover_id, title, authors, description
FROM books
WHERE embedding IS NULL
ORDER BY users_count DESC
LIMIT %s
"""


def to_text(title: str, authors: list[str] | None, description: str) -> str:
    """The text that represents a book in vector space."""
    author_line = ", ".join(authors or [])
    return f"{title}\n{author_line}\n{description}"[:MAX_CHARS]


if __name__ == "__main__":
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            cur.execute(SELECT_PENDING, (3,))
            for book_id, title, authors, description in cur.fetchall():
                print(f"--- {book_id} ---")
                print(to_text(title, authors, description)[:300])