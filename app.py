from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from recommender import BookRecommender

app = FastAPI() # the application object
# tell FastAPI where the template files live
templates = Jinja2Templates(directory="templates")

app.mount("/assets", StaticFiles(directory="assets"), name="assets") # makes cover_NA.png reachable from browser

recommender = BookRecommender.load()

TONES = ["All", "Happy", "Surprising", "Angry", "Suspenseful", "Sad"]

@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "title": "Book Recommender",
            "tagline": "Find your next read by describing it.",
            "book_count": len(recommender.books),
            "categories": recommender.categories,
            "tones": TONES,
        },
    )


# Form tells FastAPI to read a form field called query (... means it's required.)
@app.post("/search")
def search(
    request: Request,
    query: str = Form(...),
    category: str = Form("All"),
    tone: str = Form("All"),
): 
    results = recommender.recommend_from_query(query, category="All", tone="All")
    return templates.TemplateResponse(
        request,
        "_results.html",
        {"books": results.to_dict("records")},
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
        {"books": results.to_dict("records")},
    )

# run with uvicorn app:app --reload (reload makes server autostart when you make a change)