from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from app.recommender import BookRecommender, POPULARITY_PRESETS, POPULARITY_WEIGHT

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
            "popularity_default": "balanced"
        },
    )


# Form tells FastAPI to read a form field called query (... means it's required.)
@app.post("/search")
def search(
    request: Request,
    query: str = Form(...),
    genre: str = Form("All"),
    mood: str = Form("All"),
    popularity: str = Form("balanced"),
): 
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
        {"matches": matches},
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