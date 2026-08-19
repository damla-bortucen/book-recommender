# Notes

## Storage 

#### Negatives of the old CSV + Chroma design

The old shape: massive CSV of book rows and a Chroma folder of vectors, both loaded
into memory when the app starts. Essentially storing the same thing twice. 
Issues:
- Adding a single book means regenerating both artifacts. Making updated, current data difficult to maintain.
- Every row loads at startup even if not necessary

#### Solution: Postgres with `pgvector`

Collapses both into one table. A book row and its vector are the same row.

---

## pgvector

`CREATE EXTENSION vector;` adds a `vector` column type plus distance operators.

```sql
embedding VECTOR(512)
```
The number is the dimension (how many floats per vector) and it must match whatever the
embedding model outputs. 

Distance operators:

| Operator | Meaning |
| --- | --- |
| `<=>` | cosine distance |
| `<->` | L2 / Euclidean |
| `<#>` | negative inner product |

Cosine distance runs 0 (identical) → 2 (opposite), so **similarity = `1 - (a <=> b)`**.

OpenAI's vectors are unit-normalised, which means cosine and L2 rank results identically.
The old Chroma store used L2. 
Cosine is the conventional choice.

**Except for the picks vector.** Averaging several unit vectors gives one that is *not*
unit length (the more the picks disagree, the shorter it gets). Cosine divides the length
out, so ranking is unaffected.

---

## Indexes

Without an index the database reads every row — a **Seq Scan**. Finding the 8 nearest
vectors to a book means computing distance against all 60,299 rows.

An index is a structure built in advance so the database can jump to matching rows
instead of touching them all.

#### Three structures, three jobs

| Question | Index | Why |
| --- | --- | --- |
| `users_count > 100`, `ORDER BY users_count` | **B-tree** | values sort on a line, so binary search works |
| `genres @> ARRAY['Fantasy']` | **GIN** | a row holds *six* genres, nothing to sort — so invert it: per genre, a list of row ids |
| `ORDER BY embedding <=> query` | **HNSW** | can't pre-sort by distance to a point not seen yet — build a graph of which vectors are near which, then walk it |

A B-tree can't answer the vector question at all.

#### Build indexes *after* bulk loading

An index is updated on every insert. Loading 60,000 rows into a table with four indexes
means 240,000 incremental index updates; building once at the end is one build.

Also: an index **never changes what a query returns**, only how fast. Always safe to
defer — nothing is broken while they're missing.

**One index can't be deferred: the primary key.** `ON CONFLICT (hardcover_id)` needs a
unique index on that column to detect the conflict, and `PRIMARY KEY` is what creates it.
So the rule is "defer the indexes that only serve *reads*" — anything a write depends on
has to exist during the load. (`books_users_count_idx` is in `schema.sql` rather than
`indexes.sql`; it's a read index, so it could move to `indexes.sql` too.)

#### An index is an option, not a guarantee

With a GIN index on `genres`, this still choses a Seq Scan:

```sql
SELECT title FROM books WHERE genres @> ARRAY['Dystopian'] LIMIT 10; 
```

4,629 of 60,299 books are Dystopian and only 10 were wanted, so reading rows until 10 matched beat consulting the index. The planner weighs cost and decides.

#### HNSW only works on a *constant* query vector

HNSW navigates a graph toward one fixed point, so the target has to be
a constant. A vector coming from a joined row could differ per row, so the planner can't
use the index and silently falls back to scanning.

So embed the query in Python and pass the vector as a parameter. 
For "books like these picks", fetch their vectors, average them **in Python**,
then pass the result (two fast round trips rather than one slow join).

#### Other HNSW details

- **`vector_cosine_ops` must match the operator queried with** (`<=>`). Build for cosine
  then query with `<->` and the index is silently ignored.
- **HNSW is approximate.** It may not return the exact same 8 rows as a full scan — it
  trades a little recall for a lot of speed. Tune per query with `ef_search`.

#### why `iterative_scan` is set

```sql
SET hnsw.iterative_scan = relaxed_order;  -- keep walking until LIMIT is filled
SET hnsw.ef_search = 100;                 -- candidates held while walking
```

`relaxed_order` allows results to come back not perfectly distance-ordered, which is fine
here because stage 2 re-ranks them anyway. `strict_order` preserves ordering but is slower.
Raising `ef_search` trades speed for recall.

This is also why the query pulls a pool of 200 and re-ranks down to 8: a wide first stage
leaves enough survivors for the filter and the popularity weighting to work with.

---

## Connections and the pool

A connection is not a cheap handle: it's a TCP socket, a TLS handshake, authentication,
and a backend process on the server. Paying that per request would dominate the
cost of a query that takes 45 ms.

```python
pool = ConnectionPool(DATABASE_URL, min_size=1, max_size=4, configure=_configure, open=True)
```

Open a few at startup, keep them alive, hand one out per request and take it back.
`max_size` is a ceiling on concurrent database work, not a target — Postgres runs a process
per connection, so more is not better.

#### `configure` runs per connection, not per query

```python
def _configure(conn):
    register_vector(conn)
    conn.execute("SET hnsw.iterative_scan = relaxed_order")
```

Two things here are **per-connection state**, which is exactly why they belong in the hook:

- `SET` applies to the session. A connection that skipped the hook would quietly use
  default HNSW behaviour, so identical requests would perform differently depending on
  which connection they landed on.
- `register_vector` teaches *that* connection's psycopg how to send a Python list as a
  `vector` and how to read one back. Type adapters are registered per connection, not
  globally.

Because of the adapter, a vector comes back as a `Vector` object rather than a list — hence
`row[0].to_list()` before averaging the picks.

---

## Upserts

```sql
INSERT INTO books (...) VALUES (...)
ON CONFLICT (hardcover_id) DO UPDATE SET ...
```

Insert if new, update if the key already exists. This is what makes the ingest script
re-runnable — run it twice and you get the same 60k books, not 120k. `EXCLUDED` refers to
the row that *would* have been inserted.

#### Letting the data track its own staleness

A stored vector is only valid for the description it was made from, so the upsert throws
it away when that description changes:

```sql
embedding = CASE
    WHEN books.description IS DISTINCT FROM EXCLUDED.description THEN NULL
    ELSE books.embedding
END
```

`IS DISTINCT FROM`, not `<>` because `NULL <> NULL` evaluates to `NULL`, not `TRUE` 

---

## Query-writing patterns

#### Values can be parameters; identifiers cannot

`TOP_TAGS` is the one query built with `.format()`, because a **column name** can't be a
bind parameter — placeholders stand in for values only:

```python
sql = TOP_TAGS.format(column=column)
```

#### `unnest` to count array values

Tags are stored as arrays, so counting how often each one appears means expanding the
array into rows first:

```sql
SELECT tag FROM books, unnest(genres) AS tag GROUP BY tag ORDER BY count(*) DESC LIMIT 20
```

One row per (book, tag) pair, then an ordinary `GROUP BY`.

---

## Weighting recommendations by popularity

```sql
ORDER BY (1 - (embedding <=> %(q)s)) + %(w)s * ln(1 + users_count) DESC
```

Semantic similarity plus log-scaled popularity. `w = 0` is pure meaning-matching; raising
it pulls better-known books up.

`ln()` matters: reader counts can be massive, so raw counts would completely swamp the
similarity term. The log compresses that range so popularity nudges rather than dominates.

---

## API issues to remember

**A 200 doesn't mean success.**
Open Library returns `200 OK` with a 43-byte blank image for covers it doesn't have. The
browser sees a successful load, so `<img onerror>` never fires and you get a grey box.
`?default=false` makes it return a real 404. *Check what an API does on the missing case,
not just the happy path.*

**GraphQL puts errors inside a 200 response.**
`raise_for_status()` passes; the error is in the JSON body. Always check for an `errors`
key or failures look like empty results.

**Deep pagination needs a total order.**
`order_by: {users_count: desc}` isn't enough — thousands of books share `users_count = 25`
and the database may order ties differently per request, so paging duplicates and skips
rows. Add a unique tiebreaker: `order_by: [{users_count: desc}, {id: asc}]`.

**Read the token format.** Hardcover's token already includes the `Bearer ` prefix. Adding
a second one gives "Unable to verify token", which reads like an expired token.

---

## Keeping the catalogue fresh

The catalogue goes stale, so a scheduled GitHub Action re-runs the pipeline weekly to re-ingest books and update embeddings.

This workflow runs on a clock, tests nothing and deploys nothing. GitHub Actions is a
general-purpose event runner for this **scheduled ETL job**.

#### Actions vs. cron

The first row decided it. On macOS plain `cron` doesn't fire at all if the machine is
asleep at that moment (`launchd` with `StartCalendarInterval` does catch up on wake) — so a
weekly laptop job realistically runs about half the time.

Remember about the scheduler:
- **Scheduled workflows are disabled after 60 days of repo inactivity.** It emails you and
  then silently stops.

---

## Embeddings

- Default in LangChain is `text-embedding-ada-002` — the *legacy* model. Naming a model
  explicitly is worth it: `text-embedding-3-small` is 5× cheaper and scores better.
- `text-embedding-3-small` supports a `dimensions` parameter. Dropping 1536 → 512 cuts
  storage to a third with little quality loss.
