"""Recommendation engine backed by Postgres + pgvector."""

import os

from dotenv import load_dotenv
from openai import OpenAI
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.queries import PICKED_VECTORS, SEARCH, SIMILAR_TO_PICKS, TOP_TAGS

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

    def __init__(self, pool: ConnectionPool, genres: list[str], moods: list[str]):
        self.pool = pool
        self.genres = genres
        self.moods = moods


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
        return cls(pool, genres, moods)


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

        params = {
                "vec": average,
                "exclude": picks,
                "pool": CANDIDATE_POOL,
                "weight": weight,
                "limit": limit,
        }
        with conn.cursor(row_factory=dict_row) as cur:
            return cur.execute(SIMILAR_TO_PICKS, params).fetchall()


    """
    def recommend_from_query(
            self,
            query: str,
            category: str = None,
            tone: str = None,
            initial_top_k: int = INITIAL_TOP_K,
            final_top_k: int = RESULTS_TOP_K,
    ) -> pd.DataFrame:

        recs = self.db_books.similarity_search(query, k=initial_top_k)
        books_list = [int(rec.page_content.strip('"').split()[0]) for rec in recs]
        
        rank = {isbn: i for i, isbn in enumerate(books_list)}
        book_recs = self.books[self.books["isbn13"].isin(books_list)].copy() # isin keeps DataFrame order, not similarity order
        # use rank to preserve similarity order (Chroma returns nearest first)
        book_recs = book_recs.sort_values(by="isbn13", key=lambda s: s.map(rank))

        # Narrow, then rank, then cut — doing .head() first would mean the tone
        # sort only reshuffles books that similarity had already picked.
        if category != "All":
            book_recs = book_recs[book_recs["simple_categories"] == category]

        if tone in TONE_COLUMN:
            book_recs = book_recs.sort_values(by=TONE_COLUMN[tone], ascending=False)

        return book_recs.head(final_top_k)
    
    
    def recommend_from_books(
            self, 
            picks: list, 
            initial_top_k: int = INITIAL_TOP_K,
            final_top_k: int = RESULTS_TOP_K,
    ):

        picks = [p for p in picks if p]            # drop blank dropdowns
        picks = list(dict.fromkeys(picks))         # drop duplicate picks, keep order
        if not picks:
            return self.books.head(0)              # nothing chosen -> empty result

        selected = self.books[self.books["isbn13"].isin(picks)]
        allowed_categories = set(selected["simple_categories"])

        avg = np.mean(self.embeddings.embed_documents(selected["description"].tolist()), axis=0).tolist()

        recs = self.db_books.similarity_search_by_vector(avg, k=initial_top_k)
        isbns = [int(r.page_content.strip('"').split()[0]) for r in recs]

        rank = {isbn: i for i, isbn in enumerate(isbns)}
        book_recs = self.books[self.books["isbn13"].isin(isbns)].copy()
        book_recs = book_recs.sort_values(by="isbn13", key=lambda s: s.map(rank))
        book_recs = book_recs[~book_recs["isbn13"].isin(picks)]
        book_recs = book_recs[book_recs["simple_categories"].isin(allowed_categories)]  
        
        return book_recs.head(final_top_k)

    def search_titles(self, query: str, limit: int = 5):
        if not query.strip():
            return []
        mask = self.books["title"].str.contains(query, case=False, na=False, regex=False)
        hits = self.books[mask].head(limit)
        return hits[["isbn13", "title", "authors"]].to_dict("records")
    """