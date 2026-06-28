from fastapi import FastAPI

app = FastAPI() # the application object
# the server (uvicorn) runs THIS object.

@app.get("/")
def home():
    return {"message": "book recommender server!"}

# run with uvicorn app:app --reload (reload makes server autostart when you make a change)