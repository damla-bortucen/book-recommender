CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS books (
    hardcover_id     INTEGER PRIMARY KEY,
    slug             TEXT,
    title            TEXT NOT NULL,
    subtitle         TEXT,
    authors          TEXT[],
    description      TEXT NOT NULL,
    cover_url        TEXT,
    isbn13           TEXT,
    release_year     INTEGER,
    pages            INTEGER,
    rating           REAL,
    ratings_count    INTEGER,
    users_count      INTEGER NOT NULL,
    genres           TEXT[],
    moods            TEXT[],
    content_warnings TEXT[],
    embedding        VECTOR(512),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS books_users_count_idx ON books (users_count DESC);

CREATE INDEX IF NOT EXISTS books_genres_idx ON books USING gin (genres);
CREATE INDEX IF NOT EXISTS books_moods_idx  ON books USING gin (moods);

CREATE INDEX IF NOT EXISTS books_embedding_idx
    ON books USING hnsw (embedding vector_cosine_ops);