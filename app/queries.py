BOOK_COUNT = "SELECT count(*) FROM books"


TOP_TAGS = """
SELECT tag FROM books, unnest({column}) AS tag
GROUP BY tag ORDER BY count(*) DESC LIMIT %s
"""


SEARCH = """
-- stage 1: nearest books by meaning. uses the HNSW index.
WITH candidates AS (
    SELECT hardcover_id, slug, title, authors, description, cover_url,
           release_year, pages, rating, ratings_count, users_count,
           genres, moods,
           1 - (embedding <=> %(vec)s::vector) AS similarity
    FROM books
    WHERE (%(genre)s::text IS NULL OR genres @> ARRAY[%(genre)s]::text[])
      AND (%(mood)s::text  IS NULL OR moods  @> ARRAY[%(mood)s]::text[])
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