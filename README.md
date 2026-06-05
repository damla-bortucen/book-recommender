# Book Recommender

A semantic book recommendation engine that takes a natural-language prompt
(e.g. *"A book to teach children about nature"*) and returns matching books
by searching over their descriptions with vector embeddings. Results can be
narrowed by category (fiction / nonfiction) and re-ranked by emotional tone,
all through an interactive Gradio dashboard.

### Dataset
- Explored the [`dylanjcastillo/7k-books-with-metadata`](https://www.kaggle.com/datasets/dylanjcastillo/7k-books-with-metadata)
  dataset in `7k_data_exploration.ipynb`.
- Kept only books with descriptions of **≥ 20 words** to ensure enough
  signal for embeddings.
- Combined `title` and `subtitle` into a single `title_and_subtitle` field.
- Built a `tagged_description` field by prefixing each description with its
  `isbn13`, so a description can later be mapped back to a specific book.
- Exported the result to `books_cleaned.csv`.

### Vector Search & Recommendations
Built in `vector_search.ipynb`:
- Exported `tagged_description` to `tagged_description.txt` (one book per line).
- Loaded the text with LangChain's `TextLoader` and split it per-line with
  `CharacterTextSplitter` so each book is its own document.
- Embedded the documents with OpenAI embeddings and stored them in a **Chroma**
  vector store.
- Added `get_semantic_recommendation(query)`, which:
  - embeds the query into the same vector space as the book descriptions,
  - runs a similarity search to find the nearest descriptions,
  - recovers each result's `isbn13` from its tagged description,
  - looks those up in the dataframe to return full book records.

### Zero-shot Text Classification
Zero-shot models can sort pieces of text into particular categories without having been explicitly trained to do so. 

Used in `text_classification.ipynb` to give every book a simple category (fiction vs nonfiction).
- used a Hugging Face `zero-shot-classification` pipeline
  (`facebook/bart-large-mnli`) to predict `Fiction` vs `Nonfiction` from a
  book's description, via `generate_predictions(sequence, categories)`.
- filled in `simple_categories` for books
- exported the labelled dataset to `books_with_categories.csv`.

The data proved too sparse to reliably classify finer genres (romance, sci-fi,
fantasy, etc.) beyond the Fiction/Nonfiction split.

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

### Dashboard
Built in `dashboard.py` — an interactive [Gradio](https://www.gradio.app/) app
that brings the pieces above together:
- Enter a free-text description of the kind of book you want.
- Optionally filter by category (`simple_categories`) and pick an emotional
  tone (Happy, Surprising, Angry, Suspenseful, Sad), which re-ranks results by
  the matching emotion score.
- `retrieve_semantic_recommendations()` runs the Chroma similarity search, then
  applies the category filter and tone sort; `recommend_books()` renders the
  results as a thumbnail gallery with truncated descriptions and formatted
  author lists (falling back to `cover_NA.png` when a book has no thumbnail).

Run it with:
```bash
python dashboard.py
```


## Tech stack
- **Python 3.12**
- **pandas** — data cleaning & exploration
- **LangChain** (`langchain-chroma`, `langchain-community`, `langchain-openai`)
- **Chroma** — vector store
- **OpenAI embeddings** — semantic search
- **transformers / torch** — zero-shot & emotion classification (Hugging Face)
- **Gradio** — interactive dashboard
- **kagglehub** — dataset download
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
3. The notebooks (in `notebooks/`) write intermediate datasets to `data/`
   (`books_cleaned.csv`, `books_with_categories.csv`, `books_with_emotions.csv`,
   `tagged_description.txt`) that are gitignored. Run them in order —
   `7k_data_exploration` → `text_classification` → `sentiment_analysis` →
   `vector_search` — to regenerate everything before launching the dashboard.
4. Launch the dashboard from the project root:
   ```bash
   python dashboard.py
   ```

## Future Improvements
- semantic book recommendations
- improve UI
- host on the web?
- save books functionality
- more emotions?
- book recommendations based on 3 chosen books
- more recent and bigger dataset

###### Acknowledgments
["Build a Semantic Book Recommender with LLMs"](https://www.youtube.com/watch?v=Q7mS1VHm3Yw)
