"""Recommendation engine backed by Postgres + pgvector."""

import os

from dotenv import load_dotenv
from openai import OpenAI
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.queries import PICKED_VECTORS, SEARCH, SIMILAR_TO_PICKS, TOP_TAGS, SEARCH_TITLES, BOOK_COUNT

load_dotenv()

EMBED_MODEL = "text-embedding-3-small"
EMBED_DIMENSIONS = 512      # must match the VECTOR(512) column
RESULTS_TOP_K = 9
POPULARITY_WEIGHT = 0.05    # how strongly reader count nudges the ranking
CANDIDATE_POOL = 200

client = OpenAI()


def _configure(conn) -> None:
    register_vector(conn)   # make Postgres vector values come back as Vector objects
    conn.autocommit = True

    # keep walking the HNSW graph until LIMIT is filled
    # doesnt guarantee distance order but faster
    conn.execute("SET hnsw.iterative_scan = relaxed_order") 

    # how many candidate nodes to hold while walking the graph
    conn.execute("SET hnsw.ef_search = 100")


class BookRecommender:
    """
    Owns the connection pool and turns a request into a list of book rows.
    """

    def __init__(self, pool: ConnectionPool, genres: list[str], moods: list[str], book_count: int):
        # A connection is an open, authenticated network conversation with Postgres — a socket, a TLS handshake, a login
        # Opening one takes time so open multiple at the beginning and keep them alive in the "pool"
        # pool.connection() gets one that nobody is using
        self.pool = pool 

        self.genres = genres
        self.moods = moods
        self.book_count = book_count


    @classmethod
    def load(cls, tag_limit: int = 20) -> "BookRecommender":
        pool = ConnectionPool(
            os.environ["DATABASE_URL"],
            min_size=1,
            max_size=4,
            configure=_configure,   # each new connection learns the vector type
            open=True,
        )
        genres = cls._top_tags(pool, "genres", tag_limit)
        moods = cls._top_tags(pool, "moods", tag_limit)
        with pool.connection() as conn:
            book_count = conn.execute(BOOK_COUNT).fetchone()[0] # count returned as a tuple so [0] needed
        return cls(pool, genres, moods, book_count)


    @staticmethod
    def _top_tags(pool: ConnectionPool, column: str, limit: int) -> list[str]:
        """
        Most-used values from a tag array column, for the filter dropdowns.
        """

        sql = TOP_TAGS.format(column=column)   # our own literal, never user input
        with pool.connection() as conn:
            rows = conn.execute(sql, (limit,)).fetchall()
        return [row[0] for row in rows]


    @staticmethod
    def embed_query(text: str) -> list[float]:
        """
        Turn search text into a vector in the same space as the books.
        """

        response = client.embeddings.create(
            model=EMBED_MODEL, input=[text], dimensions=EMBED_DIMENSIONS
        )
        return response.data[0].embedding


    def recommend_from_query(
        self,
        query: str,
        genre: str | None = None,
        mood: str | None = None,
        weight: float = POPULARITY_WEIGHT,
        limit: int = RESULTS_TOP_K,
    ) -> list[dict]:
        """
        The books whose descriptions are nearest to the query.
        """
    
        params = {
            "vec": self.embed_query(query),
            "genre": genre if genre and genre != "All" else None,
            "mood": mood if mood and mood != "All" else None,
            "pool": CANDIDATE_POOL,
            "weight": weight,
            "limit": limit,
        }
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                return cur.execute(SEARCH, params).fetchall()


    def recommend_from_books(
        self,
        picks: list[int],
        weight: float = POPULARITY_WEIGHT,
        limit: int = RESULTS_TOP_K,
    ) -> list[dict]:
        """
        Books similar to a set of picked books, excluding the picks themselves.
        """

        picks = list(dict.fromkeys(p for p in picks if p))   # drop blanks, keep order
        if not picks: return []

        with self.pool.connection() as conn:
            # 1. fetch the picked books' stored vectors
            rows = conn.execute(PICKED_VECTORS, {"ids": picks}).fetchall()
            if not rows: return []

            # average them
            vectors = [row[0].to_list() for row in rows]
            average = [sum(values) / len(values) for values in zip(*vectors)]

            # 2. search with the average, still on the same connection
            params = {
                "vec": average,
                "exclude": picks,
                "pool": CANDIDATE_POOL,
                "weight": weight,
                "limit": limit,
            }
            with conn.cursor(row_factory=dict_row) as cur:
                return cur.execute(SIMILAR_TO_PICKS, params).fetchall()


    def search_titles(self, query: str, limit: int = 5) -> list[dict]:
        """
        Books whose title contains the query, most-read first.
        """

        query = query.strip()
        if len(query) < 2:
            return []

        params = {"pattern": f"%{query}%", "limit": limit}
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                return cur.execute(SEARCH_TITLES, params).fetchall()