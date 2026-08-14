"""
Pull the Hardcover catalogue into Postgres. 
Safe to re-run: upserts (update + insert) on hardcover_id.
"""

import os
import time

import httpx
import psycopg
from dotenv import load_dotenv

load_dotenv()


API_URL = "https://api.hardcover.app/v1/graphql"
MIN_USERS = 25       # only books with at least this many readers
TOKEN = os.environ["HARDCOVER_TOKEN"]


QUERY = """
query Books($limit: Int!, $minUsers: Int!) {
  books(
    limit: $limit
    where: {users_count: {_gte: $minUsers}}
    order_by: [{users_count: desc}, {id: asc}]
  ) {
    id title users_count
  }
}
"""


def fetch(limit: int) -> list[dict]:
    response = httpx.post(
        API_URL,
        json={"query": QUERY, "variables": {"limit": limit, "minUsers": MIN_USERS}},
        headers={"Authorization": TOKEN},
        timeout=60.0,
    )
    response.raise_for_status()
    payload = response.json()
    if "errors" in payload:              # GraphQL reports errors inside a 200
        raise RuntimeError(payload["errors"])
    return payload["data"]["books"]


if __name__ == "__main__":
    for book in fetch(5):
        print(f'{book["users_count"]:>6,}  {book["title"]}')