from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

app = FastAPI() # the application object
# the server (uvicorn) runs THIS object.

# tell FastAPI where the template files live
templates = Jinja2Templates(directory="templates")

@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {"title": "Book Recommender", "tagline": "Find your next read by describing it."}
    )

# run with uvicorn app:app --reload (reload makes server autostart when you make a change)