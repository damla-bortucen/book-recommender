# Book Recommender

A semantic book recommendation engine that takes a natural-language prompt
(e.g. *"A book to teach children about nature"*) and returns matching books
by searching over their descriptions with vector embeddings.

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


## Tech stack
- **Python 3.12**
- **pandas** — data cleaning & exploration
- **LangChain** (`langchain-chroma`, `langchain-community`, `langchain-openai`)
- **Chroma** — vector store
- **OpenAI embeddings** — semantic search
- **kagglehub** — dataset download
- **seaborn / matplotlib** — exploratory plots

## Setup
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Create a `.env` file in the project root with your OpenAI key:
   ```
   OPENAI_API_KEY=sk-...
   ```

## Plan
- semantic book recommendations
- book recommendations based on chosen book/books
- more recent and bigger dataset
