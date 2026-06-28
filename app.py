from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates

from recommender import BookRecommender

app = FastAPI() # the application object

# tell FastAPI where the template files live
templates = Jinja2Templates(directory="templates")

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

# run with uvicorn app:app --reload (reload makes server autostart when you make a change)