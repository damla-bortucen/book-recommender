from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from app.recommender import (
    BookRecommender,
    POPULARITY_PRESETS,
    POPULARITY_WEIGHT,
    MIN_TYPEAHEAD_CHARS,
    MIN_SEARCH_CHARS,
    MAX_SEARCH_CHARS,
)

app = FastAPI() # the application object
# tell FastAPI where the template files live
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static") # make static reachable from browser

recommender = BookRecommender.load()


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "title": "BookMarked",
            "tagline": "Find your next read by describing it.",
            "book_count": recommender.book_count,
            "genres": ["All"] + recommender.genres,
            "moods": ["All"] + recommender.moods,
            "popularity_presets": list(POPULARITY_PRESETS),
            "popularity_default": "balanced",
            "min_search_chars": MIN_SEARCH_CHARS,   # drives the input's minlength
            "max_search_chars": MAX_SEARCH_CHARS,   # and its maxlength
        },
    )


# Form tells FastAPI to read a form field called query (... means it's required.)
@app.post("/search")
def search(
    request: Request,
    # Form("") rather than Form(...): a required field 422s on an empty submit.
    # So clicking Search with an empty box does nothing with Form(...).
    # Answer with with message instead.
    query: str = Form(""),
    genre: str = Form("All"),
    mood: str = Form("All"),
    popularity: str = Form("balanced"),
):
    # Truncate rather than refuse: maxlength on the input means a real user
    # never gets here
    query = query.strip()[:MAX_SEARCH_CHARS]
    if len(query) < MIN_SEARCH_CHARS:
        return templates.TemplateResponse(
            request,
            "_results.html",
            {"books": [], "notice": "Describe what you're after in a few more words."},
        )

    weight = POPULARITY_PRESETS.get(popularity, POPULARITY_WEIGHT)      # rejects anything not on dict (fallback)
    results = recommender.recommend_from_query(query, genre=genre, mood=mood, weight=weight)
    return templates.TemplateResponse(
        request,
        "_results.html",
        {"books": results},
    )


@app.get("/book-search")
def book_search(request: Request, q: str = ""):
    matches = recommender.search_titles(q)
    return templates.TemplateResponse(
        request,
        "_book_options.html",
        # `searched` separates "no matches" from "not enough typed yet" — the
        # template needs to say nothing in the second case, and the engine's
        # threshold is the one that decides
        {"matches": matches, "q": q.strip(),
         "searched": len(q.strip()) >= MIN_TYPEAHEAD_CHARS},
    )


@app.post("/recommend-from-books")
def find_similar(request: Request, picks: list[int] = Form([])):
    results = recommender.recommend_from_books(picks)
    return templates.TemplateResponse(
        request,
        "_results.html",
        {"books": results},
    )


@app.get("/book/{book_id}")
def book_detail(request: Request, book_id: int):
    book = recommender.get_book(book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    return templates.TemplateResponse(
        request,
        "_book_detail.html",
        {"book": book},
    )

# run with uvicorn app.main:app --reload (reload makes server autostart when you make a change)