"""
Test HTTP routes 
Integration tests: import app/main to open a real connection pool and run tests against real live database
"""

import re

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.recommender import RESULTS_TOP_K


@pytest.fixture(scope="module")     # creates the client once for the whole file to use
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def a_book_id(client):
    """
    A hardcover_id that really exists, discovered through the typeahead.
    """

    response = client.get("/book-search", params={"q": "dune"})     # doesnt hardcode id in case of changes in Hardcover
    match = re.search(r'data-id="(\d+)"', response.text)
    assert match, "typeahead returned nothing to test with"
    return int(match.group(1))


def test_home_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "books to explore" in response.text


def test_search_returns_a_full_page_of_cards(client):
    response = client.post(
        "/search",
        data={"query": "a book about the sea", "genre": "All", "mood": "All"},
    )
    assert response.status_code == 200
    assert response.text.count("<article") == RESULTS_TOP_K


def test_search_with_a_filter_still_returns_results(client):
    response = client.post(
        "/search",
        data={"query": "adventure", "genre": "Fantasy", "mood": "All"},
    )
    assert response.status_code == 200
    assert "<article" in response.text


def test_book_detail_renders(client, a_book_id):
    response = client.get(f"/book/{a_book_id}")
    assert response.status_code == 200
    assert "Genres" in response.text


def test_unknown_book_is_404(client):
    response = client.get("/book/999999999")
    assert response.status_code == 404


def test_non_numeric_book_id_is_rejected(client):
    response = client.get("/book/not-a-number")
    assert response.status_code == 422


def test_recommend_from_books(client, a_book_id):
    response = client.post("/recommend-from-books", data={"picks": [a_book_id]})
    assert response.status_code == 200
    assert "<article" in response.text


def test_apostrophe_style_does_not_matter(client):
    """
    Hardcover titles use both ' and ’, so either spelling must find the same books.
    """

    straight = client.get("/book-search", params={"q": "handmaid's tale"})
    curly = client.get("/book-search", params={"q": "handmaid\u2019s tale"})

    straight_ids = re.findall(r'data-id="(\d+)"', straight.text)
    curly_ids = re.findall(r'data-id="(\d+)"', curly.text)

    assert straight_ids, "no results for a straight apostrophe"
    assert straight_ids == curly_ids
