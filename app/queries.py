BOOK_COUNT = "SELECT count(*) FROM books"


TOP_TAGS = """
SELECT (array_agg(tag ORDER BY n DESC))[1] AS label
FROM (
    SELECT tag, count(*) AS n
    FROM books, unnest({column}) AS tag
    GROUP BY tag
) t
WHERE lower(tag) <> ALL(%(blocked)s)
GROUP BY lower(tag)
ORDER BY sum(n) DESC
LIMIT %(limit)s
"""
# groups case variants together, then labels the group with its commonest
# spelling — "Science Fiction" (11,249) rather than "Science fiction" (2,455)


SEARCH = """
-- stage 1: nearest books by meaning. uses the HNSW index.
WITH candidates AS (
    SELECT hardcover_id, slug, title, authors, description, cover_url,
           release_year, pages, rating, ratings_count, users_count,
           genres, moods,
           1 - (embedding <=> %(vec)s::vector) AS similarity
    FROM books
    WHERE (%(genre)s::text IS NULL OR EXISTS (
        SELECT 1 FROM unnest(genres) g WHERE lower(g) = lower(%(genre)s)))
    AND (%(mood)s::text IS NULL OR EXISTS (
        SELECT 1 FROM unnest(moods) m WHERE lower(m) = lower(%(mood)s)))
    ORDER BY embedding <=> %(vec)s::vector
    LIMIT %(pool)s
)
-- stage 2: re-rank those 200 rows by meaning *and* number of readers. 
SELECT * FROM candidates
ORDER BY similarity + %(weight)s * ln(1 + users_count) DESC
LIMIT %(limit)s
"""
# typecast to vector so <=> knows to treat the incoming arraty as vector


PICKED_VECTORS = """
SELECT embedding FROM books WHERE hardcover_id = ANY(%(ids)s::int[])
"""


# Search from the average of some picked books, excluding the picks themselves.
SIMILAR_TO_PICKS = """
WITH candidates AS (
    SELECT hardcover_id, slug, title, authors, description, cover_url,
           release_year, pages, rating, ratings_count, users_count,
           genres, moods,
           1 - (embedding <=> %(vec)s::vector) AS similarity
    FROM books
    WHERE hardcover_id <> ALL(%(exclude)s::int[])
    ORDER BY embedding <=> %(vec)s::vector
    LIMIT %(pool)s
)
SELECT * FROM candidates
ORDER BY similarity + %(weight)s * ln(1 + users_count) DESC
LIMIT %(limit)s
"""


SEARCH_TITLES = """
SELECT hardcover_id, title, authors, cover_url, users_count
FROM books
WHERE translate(title, $$’‘$$, $$''$$) ILIKE %(pattern)s
ORDER BY users_count DESC
LIMIT %(limit)s
"""
# ILIKE is case insensitive LIKE
# translate() folds curly quotes to straight ones: Hardcover's titles use both,
# so a literal match misses "The Handmaid’s Tale" when you type a normal '


BOOK_DETAIL = """
SELECT hardcover_id, slug, title, authors, description, cover_url,
       isbn13, release_year, pages, rating, ratings_count, users_count,
       genres, moods, content_warnings
FROM books
WHERE hardcover_id = %(id)s
"""