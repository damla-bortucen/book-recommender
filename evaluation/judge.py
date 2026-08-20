""" Score open-ended queries by asking a model whether each result fits - LLM-as-a-Judge """

import json
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from app.recommender import BookRecommender
from evaluation.queries import QUERIES

load_dotenv()

client = OpenAI()

# pinned to a version for consistency
JUDGE_MODEL = "gpt-5.4-mini-2026-03-17"

CACHE_PATH = Path(__file__).parent / "judgments.json"

PROMPT = """You are judging a book recommendation.

A reader searched for: "{query}"

The system returned this book:
Title: {title}
Author: {authors}
Description: {description}

A search may state several constraints at once — topic, audience, format, tone,
or things to avoid. A good recommendation satisfies ALL of them, not just the
topic.

Answer NO if the book breaks any stated constraint, however well it matches the
subject: an adult book when the reader asked for children's books; a novel when
they asked for short stories

Would this book be a good recommendation for that search?
Answer with one word only: YES or NO."""


def load_cache() -> dict:
    return json.loads(CACHE_PATH.read_text()) if CACHE_PATH.exists() else {}


def save_cache(cache: dict) -> None:
    CACHE_PATH.write_text(json.dumps(cache, indent=2, sort_keys=True))


def judge(query: str, book: dict, cache: dict) -> bool:
    """True if the judge thinks this book answers the query."""

    PROMPT_VERSION = 2

    key = f"v{PROMPT_VERSION}|{query}|{book['hardcover_id']}"

    if key in cache:
        return cache[key]

    prompt = PROMPT.format(
        query=query,
        title=book["title"],
        authors=", ".join(book["authors"] or ["unknown"]),
        description=(book["description"] or "")[:1000],
    )
    response = client.chat.completions.create(
        model=JUDGE_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    verdict = response.choices[0].message.content.strip().upper().startswith("YES")

    cache[key] = verdict
    return verdict


def main() -> None:
    recommender = BookRecommender.load()
    cache = load_cache()
    total = 0.0

    for query in QUERIES:
        books = recommender.recommend_from_query(query)
        verdicts = [judge(query, book, cache) for book in books]

        precision = sum(verdicts) / len(verdicts)
        total += precision

        marks = "".join("+" if v else "." for v in verdicts)
        print(f"{precision:4.2f}  {marks}  {query}")

    save_cache(cache)
    print(f"\nmean precision@8: {total / len(QUERIES):.3f}")


if __name__ == "__main__":
    main()