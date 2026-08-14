# Book Recommender

A semantic book recommendation engine. Describe the book you want in plain language —
*"a book to teach children about nature"* and it returns matching books by comparing
your phrasing against ~60k book descriptions in vector space. Or pick up to three books
you already love and get recommendations from the average of their vectors.

Built on the [Hardcover](https://hardcover.app) catalogue, stored in **Postgres +
pgvector**, served by **FastAPI + HTMX**.

```bash
uvicorn app.main:app --reload
```

---

## How it works

There's one table and a row contains the book information and its vector.

```
Hardcover GraphQL API  ──▶  books (Postgres + pgvector)  ──▶  FastAPI + HTMX
```

### 1. Ingest — `data_ingest/hardcover.py`

Pages the full Hardcover catalogue, keeping books with a description and **at least 25 readers**.

Hardcover's `cached_tags` are split into `genres`, `moods`, and `content_warnings` arrays,
ordered most-applied first. 
Re-running the script refreshes the catalogue instead of duplicating it.

### 2. Embed — `data_ingest/embeddings.py`

Each book is represented as `title / authors / description` and embedded with a
`text-embedding-3-small` vector at **512 dimensions**, stored in the `embedding` column.

### 3. Search — `app/recommender.py` + `app/queries.py`

Every search is **two stages in one query**:

```sql
-- stage 1: nearest neighbours, via the HNSW index
WITH candidates AS (
    SELECT ..., 1 - (embedding <=> %(vec)s::vector) AS similarity
    FROM books
    WHERE (%(genre)s::text IS NULL OR genres @> ARRAY[%(genre)s]::text[])
    ORDER BY embedding <=> %(vec)s::vector
    LIMIT 200
)
-- stage 2: re-rank those 200 by meaning *and* readership
SELECT * FROM candidates
ORDER BY similarity + %(weight)s * ln(1 + users_count) DESC
LIMIT 9;
```

The `ln()` is used because otherwise reader counts (spanning 25 → 18,341) overpower the similarity
ranking completely. Log compresses the range so popularity only has a slight impact on results.

Filter in stage 1, so a genre or mood narrows the candidate pool rather than
shrinking the final nine.

**Find by books** fetches the picked books' stored vectors, averages them in Python,
and searches with the result, excluding the picks from their own results.

### 4. Web app — `app/main.py`

FastAPI serving Jinja templates with [HTMX](https://htmx.org/), styled with Tailwind.
No build step, no SPA — routes return HTML fragments that get swapped into the page.

- **Search by description** - free-text query, optional genre and mood filters.
- **Find by books** - a debounced title typeahead (`ILIKE`, most-read first); pick up to
  three and get recommendations from your average taste vector.
- Results render as a cover gallery, falling back to a placeholder when a book has no cover.

---

Notes on the reasoning behind design choices are in `NOTES.md`. 

---

## Tech stack

- **Python 3.12**
- **Postgres + [pgvector](https://github.com/pgvector/pgvector)** — books and embeddings in one table
- **psycopg 3** — connection pooling, named-parameter SQL
- **OpenAI `text-embedding-3-small`** — 512-dimension embeddings
- **[Hardcover](https://hardcover.app) GraphQL API** — source catalogue
- **FastAPI + Uvicorn** — web app and server
- **HTMX + Jinja2** — server-rendered, dynamic UI (no SPA build)
- **Tailwind CSS** — styling, via the standalone CLI

---

## Setup

**1. Install dependencies**

```bash
pip install -r requirements.txt
```

**2. Create `.env` in the project root**

```
DATABASE_URL=postgresql://user@localhost:5432/books
OPENAI_API_KEY=sk-...
HARDCOVER_TOKEN=...
```

Hardcover's token already includes the `Bearer ` prefix — don't add a second one, or you
get "Unable to verify token", which reads like an expired key.

**3. Create the table** (needs Postgres with the `vector` extension available)

```bash
psql "$DATABASE_URL" -f db/schema.sql
```

**4. Load the catalogue, then embed it**

```bash
python -m data_ingest.hardcover     # ~60k books, rate-limited to 60 req/min
python -m data_ingest.embeddings    # batches of 200; safe to interrupt and resume
```

**5. Build the indexes** — after the load, not before

```bash
psql "$DATABASE_URL" -f db/indexes.sql
```

**6. Run it**

```bash
uvicorn app.main:app --reload
```

---

## Project layout

```
app/
  main.py          FastAPI routes
  recommender.py   BookRecommender — connection pool, embedding, search
  queries.py       all SQL, as named constants
data_ingest/
  hardcover.py     catalogue → Postgres (re-runnable upsert)
  embeddings.py    descriptions → vectors (resumable)
db/
  schema.sql       table + pgvector extension
  indexes.sql      B-tree / GIN / HNSW, built after loading
templates/         index.html + HTMX partials
static/            generated CSS, picker JS, fallback cover
NOTES.md           working notes on storage, pgvector, indexing, API behaviour
README.md
```

---

## Future improvements

- evaluation/testing
- deployment
- let the popularity weight be tuned from the UI
- use `content_warnings` as an exclusion filter
- incremental refresh to keep books up to date

###### Acknowledgments
Started from ["Build a Semantic Book Recommender with LLMs"](https://www.youtube.com/watch?v=Q7mS1VHm3Yw);
the data source, storage layer, and web app have since been rebuilt.
