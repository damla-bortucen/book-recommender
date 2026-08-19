"""The 512-dimension contract: recommender, ingest and schema must agree."""

import re
from pathlib import Path

from app.recommender import EMBED_DIMENSIONS
from data_ingest.embeddings import DIMENSIONS

ROOT = Path(__file__).resolve().parent.parent

def schema_dimensions() -> int:
    """
    The n from the VECTOR(n) column in schema.sql.
    Use regex to read the column as text and check dimension. 
    Doesnt connect to the database so runs fast
    """

    schema = (ROOT / "db" / "schema.sql").read_text()
    match = re.search(r"VECTOR\((\d+)\)", schema, re.IGNORECASE)
    assert match, "no VECTOR(n) column found in db/schema.sql"
    return int(match.group(1))


def test_query_and_ingest_agree():
    """
    Query and ingest embeddings must be the same size.
    """

    assert EMBED_DIMENSIONS == DIMENSIONS



def test_python_agrees_with_schema():
    """
    Both constants must match the column the vectors are stored in.
    """

    assert EMBED_DIMENSIONS == schema_dimensions()