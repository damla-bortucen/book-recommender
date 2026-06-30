# Book Recommender

A semantic book recommendation engine that takes a natural-language prompt
(e.g. *"A book to teach children about nature"*) and returns matching books
by searching over their descriptions with vector embeddings. Results can be
narrowed by category (fiction / nonfiction / children's) and re-ranked by
emotional tone.
You can also pick three books you like and get a recommendation in the same
vein — all through an interactive web app (FastAPI + HTMX).

### Dataset
The recommender is built on [Open Library](https://openlibrary.org/developers/dumps)'s
monthly bulk data dumps, chosen over the earlier Kaggle/Google Books spikes to get a
larger, more recent catalogue. Built in `open_library_data_exploration.ipynb`, which
streams the multi-GB dumps line by line (they're far too big to load into memory):
- **Editions dump** — keep editions that are in **English**, published **2018 or later**,
  and have an ISBN-13. Each is keyed by its work, capturing title, subtitle, year, page
  count, cover id, and author keys.
- **Works dump** — descriptions and subjects live on the *work*, not the edition, so this
  pass fills them in (only ~2% of editions have a usable description, which is why ~5M
  editions distil down to ~100k books).
- **Authors dump** — editions only store author *keys*, so this resolves them to names.
- **Assembly** — clean the description text (strip markdown/HTML, normalise whitespace),
  keep only descriptions of **≥ 20 words**, dedupe by ISBN-13, and combine `title` +
  `subtitle` into `title_and_subtitle`. A `tagged_description` field prefixes each
  description with its `isbn13` so a search hit can be mapped back to a specific book.
- Exported the result (~100k books) to `books_cleaned.csv`. Note: Open Library's dumps
  carry no ratings, so `average_rating` is left blank.

### Vector Search & Recommendations
Built in `vector_search.ipynb`:
- Exported `tagged_description` to `tagged_description.txt` (one book per line).
- Loaded the text with LangChain's `TextLoader` and split it per-line with
  `CharacterTextSplitter` so each book is its own document.
- Embedded the documents with OpenAI embeddings and stored them in a **Chroma**
  vector store, persisted to `data/chroma_db/` so the dashboard and notebooks
  share one on-disk store.
- Added `get_semantic_recommendation(query)`, which:
  - embeds the query into the same vector space as the book descriptions,
  - runs a similarity search to find the nearest descriptions,
  - recovers each result's `isbn13` from its tagged description,
  - looks those up in the dataframe to return full book records.

### Text Classification
Used in `text_classification.ipynb` to give every book a simple category —
`Fiction`, `Nonfiction`, or `Children's`:
- **Keyword mapping first.** Open Library packs many messy subjects into one string
  (e.g. `"Fiction;Radio broadcasters in fiction;..."`), so `simplify_categories()`
  scans them for keywords: a `juvenile`/`children` signal maps to `Children's`,
  otherwise explicit fiction/nonfiction labels and a set of genre hints decide
  `Fiction` vs `Nonfiction`. (Children's is kept as one bucket — the fiction/nonfiction
  sub-split was too sparse and noisy to be useful.)
- **Zero-shot backfill.** For the minority of books the keyword mapping can't place, a
  Hugging Face `zero-shot-classification` pipeline (`facebook/bart-large-mnli`) predicts
  `Fiction` vs `Nonfiction` from the description, via `generate_predictions(sequence, categories)`.
- exported the labelled dataset to `books_with_categories.csv`.

The data proved too sparse to reliably classify finer genres (romance, sci-fi,
fantasy, etc.) beyond this split.

### Emotion Classification (Sentiment Analysis)
Used in `sentiment_analysis.ipynb` to give every book an emotional profile, so recommendations can later be tuned to 
a desired mood (e.g. joyful vs sad).
- used a Hugging Face `text-classification` pipeline
  (`j-hartmann/emotion-english-distilroberta-base`) to score descriptions
  across the six Ekman emotions plus neutral (`anger`, `disgust`, `fear`,
  `joy`, `sadness`, `surprise`, `neutral`).
- classified each description **sentence by sentence** rather than as a whole,
  since a single book description often spans several emotions.
- kept the **maximum score per emotion** across a description's sentences, via
  `calculate_max_emotion_scores(predictions)`.
- merged the per-emotion scores back onto each book by `isbn13` and exported
  the result to `books_with_emotions.csv`.

### Recommendation Engine & Web App
The recommendation logic and the UI are kept separate (the engine has no web
dependency, so it can be reused from notebooks, a CLI, or tests):

- **`app/recommender.py`** holds the `BookRecommender` engine. `BookRecommender.load()`
  reads `data/books_with_emotions.csv` and builds (or loads) the persisted Chroma
  store, so all disk/API I/O lives in one place. `recommend_from_query()` runs the
  Chroma similarity search, then applies the category filter and emotional-tone sort,
  returning a DataFrame. `recommend_from_books()` takes the chosen books, averages
  their description embeddings into a single "taste" vector, searches with it, drops
  the picks, and keeps only books whose `simple_categories` match the picks'.

- **`app/main.py`** is a [FastAPI](https://fastapi.tiangolo.com/) app that drives the
  engine and serves an [HTMX](https://htmx.org/)-powered UI (Jinja templates styled
  with [Tailwind CSS](https://tailwindcss.com/)). Two tabs:
  - **Search by description** — enter a free-text description, optionally filter by
    category and pick an emotional tone (Happy, Surprising, Angry, Suspenseful, Sad)
    to re-rank results. Submitting swaps the rendered results into the page via HTMX,
    with no full reload.
  - **Find by books** — a debounced typeahead searches titles across the ~100k books
    (no giant dropdown); pick up to three and the engine recommends similar reads.
  - Results render as a thumbnail gallery, falling back to `static/img/cover_NA.png`
    when a book has no cover.

Run it from the project root with:
```bash
uvicorn app.main:app --reload
```


## Tech stack
- **Python 3.12**
- **pandas** — data cleaning & exploration
- **LangChain** (`langchain-chroma`, `langchain-community`, `langchain-openai`)
- **Chroma** — vector store
- **OpenAI embeddings** — semantic search
- **transformers / torch** — zero-shot & emotion classification (Hugging Face)
- **FastAPI + Uvicorn** — web app and server
- **HTMX + Jinja2** — server-rendered, dynamic UI (no SPA build)
- **Tailwind CSS** — styling (built via the standalone CLI)
- **Open Library bulk dumps** — source catalogue (editions / works / authors)
- **seaborn / matplotlib** — exploratory plots

## Setup
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Create a `.env` file in the project root with your API keys:
   ```
   OPENAI_API_KEY=sk-...
   HF_TOKEN=hf_...
   ```
   (`OPENAI_API_KEY` powers the embeddings; `HF_TOKEN` is used for the
   Hugging Face classification models.)
3. Download the [Open Library data dumps](https://openlibrary.org/developers/dumps)
   (editions, works, authors) — and the ratings dump if you want it later —
   decompress them, and place them in `data/open_library/` (the notebook expects
   filenames like `ol_dump_editions_2026-05-31.txt`; update the dates in
   `open_library_data_exploration.ipynb` to match the dump you downloaded).
4. The notebooks (in `notebooks/`) write intermediate datasets to `data/`
   (`books_cleaned.csv`, `books_with_categories.csv`, `books_with_emotions.csv`,
   `tagged_description.txt`) that are gitignored. Run them in order —
   `open_library_data_exploration` → `text_classification` → `sentiment_analysis` →
   `vector_search` — to regenerate everything before launching the app.
5. Launch the app from the project root:
   ```bash
   uvicorn app.main:app --reload
   ```

## Future Improvements
- evaluation of performance
- improve UI (incl. a searchable book picker that scales to the ~100k-book catalogue)
- improve category accuracy and add finer genres
- backfill ratings from Open Library's ratings dump

###### Acknowledgments
["Build a Semantic Book Recommender with LLMs"](https://www.youtube.com/watch?v=Q7mS1VHm3Yw)
