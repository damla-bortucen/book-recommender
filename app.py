from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI() # the application object
# the server (uvicorn) runs THIS object.

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <!doctype html>
    <html>
      <head><title>Book Recommender</title></head>
      <body>
        <h1>Book Recommender</h1>
        <p>The server is alive!</p>
      </body>
    </html>
    """

# run with uvicorn app:app --reload (reload makes server autostart when you make a change)