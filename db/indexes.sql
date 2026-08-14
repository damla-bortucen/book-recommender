CREATE INDEX IF NOT EXISTS books_genres_idx ON books USING gin (genres);
CREATE INDEX IF NOT EXISTS books_moods_idx  ON books USING gin (moods);

CREATE INDEX IF NOT EXISTS books_embedding_idx
    ON books USING hnsw (embedding vector_cosine_ops);