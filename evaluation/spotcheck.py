"""
Check the LLM judge against human opinion on a small sample.
High agreement makes the judge reliable; low agreement means the prompt needs work.
"""

import json
import random
from pathlib import Path

from app.recommender import BookRecommender

CACHE_PATH = Path(__file__).parent / "judgments.json"
SAMPLE_SIZE = 20


def main() -> None:
    judgments = json.loads(CACHE_PATH.read_text())

    yes = [key for key, verdict in judgments.items() if verdict]
    no = [key for key, verdict in judgments.items() if not verdict]
    half = SAMPLE_SIZE // 2
    sample = random.sample(yes, half) + random.sample(no, half)
    random.shuffle(sample)

    recommender = BookRecommender.load()
    mine = []

    print(f"{SAMPLE_SIZE} recommendations to judge. y or n.\n")
    for i, key in enumerate(sample, start=1):
        query, book_id = key.rsplit("|", 1)
        book = recommender.get_book(int(book_id))

        print(f"--- {i}/{SAMPLE_SIZE}")
        print(f"  search: {query}")
        print(f"  book:   {book['title']} — {', '.join(book['authors'] or ['unknown'])}")
        print(f"  blurb:  {book['description'][:300].strip()}...")

        answer = ""
        while answer not in ("y", "n"):
            answer = input("  good recommendation? [y/n] ").strip().lower()
        mine.append(answer == "y")
        print()

    agreed = sum(1 for key, verdict in zip(sample, mine) if judgments[key] == verdict)
    print(f"agreement: {agreed}/{SAMPLE_SIZE} ({100 * agreed / SAMPLE_SIZE:.0f}%)\n")

    print("disagreements:")
    for key, verdict in zip(sample, mine):
        if judgments[key] != verdict:
            query, book_id = key.rsplit("|", 1)
            title = recommender.get_book(int(book_id))["title"]
            judge_said = "YES" if judgments[key] else "NO"
            you_said = "YES" if verdict else "NO"
            print(f"  judge {judge_said:<3} / you {you_said:<3}  {query} -> {title}")


if __name__ == "__main__":
    main()