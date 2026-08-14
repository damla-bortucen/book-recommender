"""Embed book descriptions into pgvector. Safe to re-run: only fills empty embeddings."""

import os

import psycopg
from dotenv import load_dotenv
from openai import OpenAI
from pgvector.psycopg import register_vector

load_dotenv()

client = OpenAI()

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

UPDATE_EMBEDDING = "UPDATE books SET embedding = %s WHERE hardcover_id = %s"


def to_text(title: str, authors: list[str] | None, description: str) -> str:
    """The text that represents a book in vector space."""
    author_line = ", ".join(authors or [])
    return f"{title}\n{author_line}\n{description}"[:MAX_CHARS]


def embed(texts: list[str]) -> list[list[float]]:
    response = client.embeddings.create(
        model=MODEL,
        input=texts,
        dimensions=DIMENSIONS,
    )
    return [item.embedding for item in response.data]


def fetch_batch(conn) -> list[tuple]:
    """
    The next batch of books that still need an embedding.
    """
    with conn.cursor() as cur:
        cur.execute(SELECT_PENDING, (BATCH_SIZE,))
        return cur.fetchall()


def save_embeddings(conn, books: list[tuple], vectors: list[list[float]]) -> None:
    """
    Write each vector back to the book it came from.
    """
    updates = []
    for book, vector in zip(books, vectors):
        book_id = book[0]
        updates.append((vector, book_id))

    with conn.cursor() as cur:
        cur.executemany(UPDATE_EMBEDDING, updates)
    conn.commit()


def main() -> None:
    done = 0
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        register_vector(conn)          # teaches psycopg to send lists as vectors

        while True:
            books = fetch_batch(conn)
            if not books:
                break

            texts = []
            for book_id, title, authors, description in books:
                texts.append(to_text(title, authors, description))

            vectors = embed(texts)
            save_embeddings(conn, books, vectors)

            done += len(books)
            print(f"{done:,} embedded")

    print(f"done: {done:,} books embedded")


if __name__ == "__main__":
    main()