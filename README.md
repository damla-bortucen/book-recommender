<p align="center">
  <img alt="header" src="https://shieldcn.dev/header/grid.svg?title=BookMarked&subtitle=Find+your+next+read+by+describing+it.&size=wide&border=false&bg=f7f4ef&titleColor=292522&subtitleColor=716a63&font=serif" />
</p>

<p align="center">
  <a href="https://github.com/damla-bortucen/bookmarked/actions/workflows/ci.yml">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://shieldcn.dev/github/ci/damla-bortucen/bookmarked.svg?workflow=ci.yml&branch=main&variant=outline&size=sm&mode=dark" />
      <img alt="CI status" src="https://shieldcn.dev/github/ci/damla-bortucen/bookmarked.svg?workflow=ci.yml&branch=main&variant=outline&size=sm&mode=light" />
    </picture>
  </a>
  <a href="https://github.com/damla-bortucen/bookmarked/commits">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://shieldcn.dev/github/last-commit/damla-bortucen/bookmarked.svg?variant=outline&size=sm&mode=dark" />
      <img alt="Last commit" src="https://shieldcn.dev/github/last-commit/damla-bortucen/bookmarked.svg?variant=outline&size=sm&mode=light" />
    </picture>
  </a>
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://shieldcn.dev/badge/python-3.12-blue.svg?logo=python&variant=outline&size=sm&mode=dark" />
    <img alt="Python 3.12" src="https://shieldcn.dev/badge/python-3.12-blue.svg?logo=python&variant=outline&size=sm&mode=light" />
  </picture>
  <a href="https://github.com/damla-bortucen/bookmarked/blob/main/LICENSE">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://shieldcn.dev/github/license/damla-bortucen/bookmarked.svg?variant=outline&size=sm&mode=dark" />
      <img alt="License: MIT" src="https://shieldcn.dev/github/license/damla-bortucen/bookmarked.svg?variant=outline&size=sm&mode=light" />
    </picture>
  </a>
</p>

## About

A semantic book recommendation engine. Describe the book you want in plain language —
*"a book to teach children about nature"* and it returns matching books by comparing
your phrasing against ~60k book descriptions in vector space. Or pick up to three books
you already love and get recommendations from the average of their vectors.

Built on the [Hardcover](https://hardcover.app) catalogue, stored in **Postgres +
pgvector**, served by **FastAPI + HTMX**.

**[Live demo →](https://bookmarked-qktw.onrender.com)**
*Hosted on Render's free tier, so the first request takes a minute to wake.*

*A walkthrough of the live app:*

https://github.com/user-attachments/assets/23bdfb9d-5306-4927-9473-6dbcee93bdd4

To run it yourself, see [Setup](#setup).

<details open="open">
<summary>Table of Contents</summary>

- [About](#about)
- [Tech stack](#tech-stack)
- [How it works](#how-it-works)
- [Setup](#setup)
- [Roadmap](#roadmap)
- [Acknowledgements](#acknowledgements)
- [License](#license)

</details>

<br>

---

<br>

## Tech stack

- **Python 3.12**
- **Postgres + [pgvector](https://github.com/pgvector/pgvector)** - books and embeddings in one table
- **psycopg 3** - connection pooling, named-parameter SQL
- **OpenAI** `text-embedding-3-small` - 512-dimension embeddings
- **[Hardcover](https://hardcover.app) GraphQL API** - source catalogue
- **FastAPI + Uvicorn** - web app and server
- **HTMX + Jinja2** - server-rendered, dynamic UI (no SPA build)
- **Tailwind CSS** - styling, via the standalone CLIyee

<br>

---

<br>

## How it works

One table. Each row holds a book and its embedding.

```
Hardcover GraphQL API  ──▶  books (Postgres + pgvector)  ──▶  FastAPI + HTMX
```

The measurements behind these choices are in [NOTES.md](NOTES.md).

### 1. Ingest - `data_ingest/hardcover.py`

Pages the full Hardcover catalogue, keeping books with a description and **at least 25 readers**.

Hardcover's `cached_tags` are split into `genres`, `moods`, and `content_warnings` arrays,
ordered most-applied first.
Re-running the script refreshes the catalogue instead of duplicating it.

### 2. Embed - `data_ingest/embeddings.py`

Each book is represented as `title / authors / description` and embedded with a
`text-embedding-3-small` vector at **512 dimensions**, stored in the `embedding` column.

### 3. Search - `app/recommender.py` + `app/queries.py`

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
LIMIT 8;
```

Reader counts span 25 → 18,341, so without the `ln()` popularity would swamp similarity
entirely; the log compresses that range into a nudge. Filtering in stage 1 means a genre
or mood narrows the candidate pool rather than shrinking the final eight.

**Find by books** averages the picked books' stored vectors and searches with the result,
excluding the picks from their own results.

### 4. Web app - `app/main.py`

FastAPI serving Jinja templates (`_results.html`, `_book_options.html`, `_book_detail.html`) with [HTMX](https://htmx.org/), 
styled with Tailwind.
No build step. Routes return HTML fragments that get swapped into the page.

- **Search by description** — free-text query, optional genre and mood filters.
- **Find by books** — a debounced title typeahead (`ILIKE`, most-read first); pick up to
  three and get recommendations from your average taste vector.
- Results render as a cover gallery, falling back to a placeholder when a book has no cover.

### 5. Refresh - `.github/workflows/refresh-catalogue.yml`

The catalogue goes stale, so a scheduled GitHub Action re-runs the pipeline weekly:

```yaml
on:
  schedule:
    - cron: "17 4 * * 0"   # Sundays 04:17 UTC
  workflow_dispatch: {}    # plus a "Run workflow" button
```

It re-fetches everything rather than syncing incrementally in a 7-day window.
Full run: 62 requests, about 3 minutes.

`DATABASE_URL`, `OPENAI_API_KEY` and `HARDCOVER_TOKEN` are stored as repository secrets.

### 6. Ship - `.github/workflows/ci.yml` + `render.yaml`

```
PR ──▶ tests ──▶ merge to main ──▶ tests ──▶ deploy hook ──▶ Render
```

Tests run on every pull request and on `main`. The deploy job `needs` the test
job, so a failing suite means no deploy at all — rather than a red build sitting
next to a broken live site.

```yaml
deploy:
  needs: test
  if: github.event_name == 'push' && github.ref == 'refs/heads/main'
```

Render's `autoDeploy` is **off**; deploys are triggered by a hook from CI, not
by the push itself. The tests are integration tests — importing `app.main` opens
a real connection pool — so CI uses the same `DATABASE_URL` and `OPENAI_API_KEY`
secrets as the refresh workflow.

| Test file | Covers |
| --- | --- |
| `tests/test_contract.py` | `EMBED_DIMENSIONS`, `DIMENSIONS` and `VECTOR(512)` still agree |
| `tests/test_routes.py` | every route returns what the templates expect |

<br>

---

<br>

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Create `.env` in the project root

```
DATABASE_URL=postgresql://user@localhost:5432/books
OPENAI_API_KEY=sk-...
HARDCOVER_TOKEN=...
```

Hardcover's token already includes the `Bearer ` prefix — don't add a second one, or you
get "Unable to verify token", which reads like an expired key.

### 3. Create the table

Needs a Postgres with the `vector` extension available.

```bash
psql "$DATABASE_URL" -f db/schema.sql
```

### 4. Load the catalogue, then embed it

```bash
python -m data_ingest.hardcover     # ~60k books, rate-limited to 60 req/min
python -m data_ingest.embeddings    # batches of 200; safe to interrupt and resume
```

### 5. Build the indexes

After the load, not before: indexing 60k rows once is far cheaper than 60k
incremental index updates, and a missing index only makes queries slow, never wrong.

```bash
psql "$DATABASE_URL" -f db/indexes.sql
```

### 6. Build the stylesheet

`static/css/tailwind.css` is generated and **not committed**, so a fresh clone has no
CSS until you build it. Render runs the same build at deploy time.

The standalone CLI is gitignored too — grab **v4.3.1**, matching the version pinned in
`render.yaml`. The URL below is the macOS arm64 build; swap the asset name for
`tailwindcss-linux-x64` or `tailwindcss-macos-x64` depending on your device:

```bash
curl -sSLo tailwindcss \
  https://github.com/tailwindlabs/tailwindcss/releases/download/v4.3.1/tailwindcss-macos-arm64
chmod +x tailwindcss
./tailwindcss -i static/css/input.css -o static/css/tailwind.css
```

### 7. Run it

```bash
uvicorn app.main:app --reload
```

While editing templates, leave the watcher running in a second terminal. Tailwind only
emits the classes it finds when it runs, so a class you just typed does nothing until a
rebuild:

```bash
./tailwindcss -i static/css/input.css -o static/css/tailwind.css --watch
```

<br>

---

<br>

## Roadmap

- use `content_warnings` as an exclusion filter
- a personal shelf (TBR) — the first feature that would need writes

<br>

---

<br>

## Acknowledgements

Started from ["Build a Semantic Book Recommender with LLMs"](https://www.youtube.com/watch?v=Q7mS1VHm3Yw);
the data source, storage layer, and web app have since been rebuilt.

<br>

---

<br>

## License

MIT — see [LICENSE](LICENSE).
