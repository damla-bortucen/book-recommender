""" Run the evaluation cases and report how often the expected book comes back. """

from app.recommender import BookRecommender
from evaluation.cases import CASES


def main() -> None:
    recommender = BookRecommender.load()
    for weight in (0.0, 0.02, 0.05, 0.1, 0.2):
        hits = 0
        for query, expected_title in CASES:
            matches = recommender.search_titles(expected_title, limit=1)
            if not matches:
                print(f"?     no book in the catalogue called {expected_title!r}")
                continue
            expected = matches[0]

            results = recommender.recommend_from_query(query, weight=weight)
            returned_ids = [book["hardcover_id"] for book in results]

            if expected["hardcover_id"] in returned_ids:
                rank = returned_ids.index(expected["hardcover_id"]) + 1
                hits += 1
                print(f"HIT  #{rank}  {expected['title']}")
            else:
                print(f"MISS      {expected['title']}  (top result was {results[0]['title']!r})")

        print(f"weight={weight}: {hits}/{len(CASES)}")


if __name__ == "__main__":
    main()