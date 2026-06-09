import os
import pandas as pd
import numpy as np
from dotenv import load_dotenv

from langchain_community.document_loaders import TextLoader
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import CharacterTextSplitter
from langchain_chroma import Chroma


class BookRecommender:
    """
    Recommendation engine: owns the books dataframe and the Chroma vector
    store, and turns a request into a ranked DataFrame of books.
    """

    def __init__(self, books: pd.DataFrame, db_books: Chroma, embeddings: OpenAIEmbeddings):
        self.books = books
        self.db_books = db_books
        self.embeddings = embeddings

    @classmethod    # classmethod can be called on a class without having an instance yet
    def load(cls, data_dir: str = "data", assets_dir: str = "assets") -> "BookRecommender":
        """
        Load the dataframe and build/load the persisted vector store.
        All disk/API I/O lives here so importing this module has no side effects.
        """
        load_dotenv()

        books = pd.read_csv(os.path.join(data_dir, "books_with_emotions.csv"))

        books["large_thumbnail"] = books["thumbnail"] + "&fife=w800"
        books["large_thumbnail"] = np.where(
            books["large_thumbnail"].isna(),
            os.path.join(assets_dir, "cover_NA.png"),
            books["large_thumbnail"],
        )

        # one embeddings client backs both the vector store and recommend_from_books,
        # so queries are always embedded with the same model the stored vectors used
        embeddings = OpenAIEmbeddings()

        chroma_dir = os.path.join(data_dir, "chroma_db")
        if os.path.exists(chroma_dir):
            # already built once so just loads the saved vectors, no API calls
            db_books = Chroma(persist_directory=chroma_dir, embedding_function=embeddings)
        else:
            # first run embeds everything once, then save it
            raw_documents = TextLoader(os.path.join(data_dir, "tagged_description.txt")).load()
            text_splitter = CharacterTextSplitter(separator="\n", chunk_size=0.1, chunk_overlap=0)
            documents = text_splitter.split_documents(raw_documents)
            db_books = Chroma.from_documents(
                documents,
                embeddings,
                persist_directory=chroma_dir   # save the vectors to a folder
            )

        return cls(books, db_books, embeddings)

    @property   # makes metod accessible like an attribute: i.e. recommender.categories
    def categories(self) -> list:
        """
        Category choices for a UI dropdown, with an "All" sentinel first.
        """
        return ["All"] + sorted(self.books["simple_categories"].unique())

    @property
    def book_choices(self) -> list:
        """
        (label, isbn13) pairs for the book-picker dropdowns. The label is
        shown to the user; the isbn13 value is what gets passed back to
        recommend_from_books.
        """
        rows = self.books.sort_values("title")
        return [(f"{row.title} by {row.authors}", row.isbn13) for row in rows.itertuples()]

    def recommend_from_query(
            self,
            query: str,
            category: str = None,
            tone: str = None,
            initial_top_k: int = 50,
            final_top_k: int = 16,
    ) -> pd.DataFrame:

        recs = self.db_books.similarity_search(query, k=initial_top_k)
        books_list = [int(rec.page_content.strip('"').split()[0]) for rec in recs]
        
        rank = {isbn: i for i, isbn in enumerate(books_list)}
        book_recs = self.books[self.books["isbn13"].isin(books_list)].copy() # reorders rows in the DataFrame's original row order
        # use rank to preserve similarity order (Chroma returns nearest first)
        book_recs = book_recs.sort_values(by="isbn13", key=lambda s: s.map(rank))

        if category != "All":
            book_recs = book_recs[book_recs["simple_categories"] == category].head(final_top_k)
        else:
            book_recs = book_recs.head(final_top_k)

        match tone:
            case "Happy":
                book_recs.sort_values(by="joy", ascending=False, inplace=True)
            case "Surprising":
                book_recs.sort_values(by="surprise", ascending=False, inplace=True)
            case "Angry":
                book_recs.sort_values(by="anger", ascending=False, inplace=True)
            case "Suspenseful":
                book_recs.sort_values(by="fear", ascending=False, inplace=True)
            case "Sad":
                book_recs.sort_values(by="sadness", ascending=False, inplace=True)

        return book_recs
    

    def recommend_from_books(
            self, 
            picks: list, 
            initial_top_k: int = 50,
            final_top_k: int = 16,
    ):
        """
        Recommend books based on a list of picked isbn13s.
        Averages the picks' embeddings, searches, drops the picks, and keeps
        only books whose simple_categories matches one of the picks'.
        """

        picks = [p for p in picks if p]            # drop blank dropdowns
        picks = list(dict.fromkeys(picks))         # drop duplicate picks, keep order
        if not picks:
            return self.books.head(0)              # nothing chosen -> empty result

        selected = self.books[self.books["isbn13"].isin(picks)]
        allowed_categories = set(selected["simple_categories"])

        avg = np.mean(self.embeddings.embed_documents(selected["description"].tolist()), axis=0).tolist()

        recs = self.db_books.similarity_search_by_vector(avg, k=initial_top_k)
        isbns = [int(r.page_content.strip('"').split()[0]) for r in recs]

        rank = {isbn: i for i, isbn in enumerate(isbns)}
        book_recs = self.books[self.books["isbn13"].isin(isbns)].copy()
        book_recs = book_recs.sort_values(by="isbn13", key=lambda s: s.map(rank))
        book_recs = book_recs[~book_recs["isbn13"].isin(picks)]
        book_recs = book_recs[book_recs["simple_categories"].isin(allowed_categories)]  
        
        return book_recs.head(final_top_k)
