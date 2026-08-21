# Notes

## 1. Storage 

### Old design: CSV + Chroma

The old system stored book data in a large CSV and vectors in Chroma, then loaded both into memory at startup. This duplicated related data and caused two problems:

- Adding one book required regenerating both artifacts.
- Every row loaded at startup, whether needed or not.

### New design: PostgreSQL + `pgvector`

Collapses both into one table. A book row and its vector are the same row.

---

## 2. `pgvector`

`CREATE EXTENSION vector;` adds a `vector` column type plus distance operators.

```sql
embedding VECTOR(512)
```
`512` is the embedding dimension and must match the model's output.

Distance operators:

| Operator | Meaning |
| --- | --- |
| `<=>` | cosine distance |
| `<->` | L2 / Euclidean |
| `<#>` | negative inner product |

Cosine distance runs 0 (identical) to 2 (opposite), so **similarity = `1 - (a <=> b)`**.

OpenAI's vectors are unit-normalised, which means cosine and L2 rank results identically.
The old Chroma store used L2. 
Cosine is the conventional choice.

**Except for the picks vector.** Averaging several unit vectors gives one that is *not*
unit length (the more the picks disagree, the shorter it gets). Cosine divides the length
out, so ranking is unaffected.

---

## 3. Indexes

Without an index, PostgreSQL performs a **sequential scan** and compares the query with all rows.

An index is a structure built in advance so the database can jump to matching rows
instead of touching them all.

#### Three structures, three jobs

| Question | Index | Why |
| --- | --- | --- |
| `users_count > 100`, `ORDER BY users_count` | **B-tree** | values sort on a line, so binary search works |
| `genres @> ARRAY['Fantasy']` | **GIN** | a row holds *six* genres, nothing to sort — so invert it: per genre, a list of row ids |
| `ORDER BY embedding <=> query` | **HNSW** | can't pre-sort by distance to a point not seen yet — build a graph of which vectors are near which, then walk it |

A B-tree can't answer the vector question at all.

### Build indexes after bulk loading

An index is updated on every insert. Loading 60,000 rows into a table with four indexes
means 240,000 incremental index updates; building once at the end is one build.

Also: an index **never changes what a query returns**, only how fast. Always safe to
defer — nothing is broken while they're missing.

**Rule:** keep indexes required by writes; defer indexes used only by reads. 
`ON CONFLICT (hardcover_id)` needs a unique index on that column to detect the conflict, 
and `PRIMARY KEY` is what creates it: Anything a write depends on has to exist during the load. 

### An index is an option, not a guarantee

With a GIN index on `genres`, this still choses a Seq Scan:

```sql
SELECT title FROM books WHERE genres @> ARRAY['Dystopian'] LIMIT 10; 
```

4,629 of 60,299 books are Dystopian and only 10 were wanted, so reading rows until 10 matched beat consulting the index. The planner weighs cost and decides.

### HNSW only works on a constant query vector

HNSW navigates a graph toward one fixed point, so the target has to be
a constant. A vector coming from a joined row could differ per row, so the planner can't
use the index and silently falls back to scanning.

So embed the query in Python and pass the vector as a parameter. 
For "books like these picks", fetch their vectors, average them **in Python**,
then pass the result (two fast round trips rather than one slow join).

### HNSW configuration

The index operator class must match the query operator. An index built with `vector_cosine_ops` is used with `<=>`; querying with `<->` can cause the index to be ignored.

HNSW is approximate: it trades some recall for speed. Recall is mainly controlled by `ef_search`.

```sql
SET hnsw.iterative_scan = relaxed_order;  -- keep walking until LIMIT is filled
SET hnsw.ef_search = 400;                 -- candidates held while walking
```

- `relaxed_order` keeps searching until enough rows satisfy `LIMIT`, without guaranteeing perfect distance order. This is acceptable because stage 2 re-ranks the results.
- Stage 1 retrieves 200 candidates; stage 2 filters and re-ranks them to 8 recommendations.


### Choosing `ef_search`

HNSW walks through neighboring vectors while retaining a shortlist of promising candidates. If the shortlist is too small, useful paths may be discarded before their best neighbors are explored.

For this setup:

```text
CANDIDATE_POOL = 200
ef_search      = 400
```

Keep `ef_search >= CANDIDATE_POOL`; roughly double is a sensible starting point. Raise both together if the candidate pool increases.

Results from 45 evaluation cases on about 61,000 books:

| `ef_search` | Hit@8 | MRR |
| ---: | ---: | ---: |
| 100 | 34/45 | 0.693 |
| 200 | 34/45 | 0.693 |
| **400** | **37/45** | **0.759** |
| 800 | 37/45 | 0.759 |

At 100, *The Metamorphosis*—the true third-ranked result for “a man wakes as an insect and his family slowly turns against him”—was absent from the top 200 candidates. A setting of 800 found nothing that 400 missed, making **400 the best trade-off** in this test.

---

## 4. Connections and pooling

Opening a connection requires a TCP socket, TLS handshake, authentication, and a server process. Repeating 
that work for every request could cost more than the query itself.

```python
pool = ConnectionPool(DATABASE_URL, min_size=1, max_size=4, configure=_configure, open=True)
```

The pool opens a few connections at startup and reuses them. `max_size` limits concurrent database work; it is a ceiling, not a target.

#### Configure runs per connection, not per query

```python
def _configure(conn):
    register_vector(conn)
    conn.execute("SET hnsw.iterative_scan = relaxed_order")
```

Both settings are connection-specific:

- `SET` changes the database session. Skipping it would make performance depend on which pooled connection handled the request.
- `register_vector` teaches that connection's psycopg adapter how to send and receive vector values.

Because the adapter returns a `Vector` object, use `row[0].to_list()` before averaging selected vectors.

---

## 5. Upserts

```sql
INSERT INTO books (...) VALUES (...)
ON CONFLICT (hardcover_id) DO UPDATE SET ...
```

Insert if new, update if the key already exists. This is what makes the ingest script
re-runnable — run it twice and you get the same 60k books, not 120k. `EXCLUDED` refers to
the row that *would* have been inserted.

A vector is valid only for the description from which it was generated. If that description changes, clear the old vector:

```sql
embedding = CASE
    WHEN books.description IS DISTINCT FROM EXCLUDED.description THEN NULL
    ELSE books.embedding
END
```

Use `IS DISTINCT FROM` instead of `<>` because it handles `NULL` values predictably.

## 6. Validation

Most outliers in this catalogue are real:

| Looks wrong | Actually |
| --- | --- |
| `release_year = -2100` | Gilgamesh. Negative years are BCE. |
| `release_year = 2030` | *The Doors of Stone* — announced, unpublished |
| `pages = 18831` | *The Complete Wheel of Time* — an omnibus |
| `pages = 0` | genuinely impossible: a placeholder for missing |

A range check written from intuition would have deleted Gilgamesh and kept the zeroes.

Some fields can't be validated at all. `release_year` values between 1 and 100 are mostly
wrong (Charlotte's Web is stored as `2`), but `Letters from a Stoic` at `64` is correct —
Seneca wrote it around 65 AD. Nothing in the row distinguishes them.

### Filter future release dates

Exclude unreleased books from the GraphQL. This stop future incorrect ingests but 
doesn't fix the 12 already stored so those were deleted with a one-off DELETE.

### Filter 0 pages

0 for page number is used as a placeholder for unknown rather than an actual value. 
So replace with None.

---

## 6. SQL patterns

### Values can be parameters; identifiers cannot

Bind parameters represent values, not column names. `TOP_TAGS` therefore uses `.format()` for its validated column identifier:

```python
sql = TOP_TAGS.format(column=column)
```

### Count array values with `unnest`

```sql
SELECT tag
FROM books, unnest(genres) AS tag
GROUP BY tag
ORDER BY count(*) DESC
LIMIT 20;
```

`unnest` creates one row per `(book, tag)` pair, after which a normal `GROUP BY` can count the tags.

---

## 7. Popularity-weighted recommendations

```sql
ORDER BY (1 - (embedding <=> %(q)s)) + %(w)s * ln(1 + users_count) DESC
```

This combines semantic similarity with log-scaled popularity:

- `w = 0` gives pure semantic matching.
- Increasing `w` favors more widely read books.
- `ln(1 + users_count)` compresses large reader counts so popularity nudges rather than dominates the ranking.

### Choosing the weight

The two evaluation tiers measure different goals and favor different weights:

| `w` | Tier 1 Hit@8: findability | Tier 2 Precision@8: quality |
| ---: | ---: | ---: |
| 0.00 | 22/45 | **0.551** |
| 0.02 | 36/45 | 0.517 |
| **0.05 (shipped)** | **37/45** | 0.500 |

- **Find a half-remembered book:** the target is often famous, so popularity nearly doubles Tier 1 performance from `w = 0` to `w = 0.05`.
- **Recommend something niche:** popularity pushes obscure but relevant books down, so Tier 2 quality falls as `w` rises.

Tier 1 is biased toward fame because its cases were written from memory. The median target book is in the **99.9th percentile** by reader count, so this tier overstates the general value of popularity.

**Conclusion:** one global weight handles two different jobs imperfectly. Exposing the popularity weight in the UI is more useful than further tuning a single constant.

---

## 8. Rejected: embedding genres and moods

**Decision: do not ship. The extra embedding produced no overall improvement.**

The original text embedded `title`, `authors`, and `description`, but not genre or mood tags. A second `embedding_v2` column added those tags so both approaches could be tested on identical queries.

| Embedding | Tier 1 | Tier 2 at `w = 0.05` |
| --- | ---: | ---: |
| Description only | **37/45** | 0.500 |
| Description + tags | 36/45 | 0.500 |

`embedding_v2` had an advantage: it used exact sequential scans because its HNSW index had not been built, while the original embedding used approximate search. It still did not improve the scores.

### What the experiment revealed

The tags were not useless. At `w = 0`, v2 surfaced short-story collections such as *Astray*, *Awayland*, and *Come On In*, which v1 missed. Stage 2 then removed them because the popularity term favored books such as *Migrations*.

In other words, **the tags worked, but popularity weighting cancelled their benefit.**

Two reasons not to ship v2:

- **Tag coverage is sparse:** only 529 of 61,052 books—0.9%—have the `Short stories` tag.
- **Filters are stronger:** `genres @> ARRAY[...]` guarantees a constraint, while embedding a tag only nudges similarity.

### Better improvement: clean the genre dropdown

The top-20 genre list contains duplicated or unhelpful values:

- `Science Fiction` and `Science fiction` differ only by capitalization.
- `Fiction` covers 56% of the corpus and barely filters anything.
- `General` is not meaningful.
- `Young Adult`/`Young Adult Fiction` and several comics/graphic-novel variants overlap.
- Roughly 6 of 20 slots are wasted, while `Horror`—1,058 books and rank 32—is missing.

Normalizing capitalization, merging duplicates, and blocking low-value labels should improve the interface more than re-embedding the catalogue.

---

## 9. API issues to remember

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

## 10. Keeping the catalogue fresh

A scheduled GitHub Action reruns the ETL pipeline weekly to re-ingest books and update embeddings. It is a scheduled data job—not a test or deployment workflow.

This workflow runs on a clock, tests nothing and deploys nothing. GitHub Actions is a
general-purpose event runner for this **scheduled ETL job**.

### Actions vs. cron

GitHub Actions is more reliable than macOS `cron` here because ordinary cron jobs do not run if the laptop is asleep at the scheduled time. One caveat: **GitHub disables scheduled workflows after 60 days of repository inactivity.**

---

## 11. Embeddings

- Default in LangChain is `text-embedding-ada-002` — the *legacy* model. Naming a model
  explicitly is worth it: `text-embedding-3-small` is 5× cheaper and scores better.
- `text-embedding-3-small` supports a `dimensions` parameter. Dropping 1536 → 512 cuts
  storage to a third with little quality loss.
