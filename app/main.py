from fastapi import FastAPI

app = FastAPI(
    title="Skating Academy API",
    version="1.0.0"
)


@app.get("/")
def root():
    return {
        "message": "Skating Academy Backend Running 🚀"
    }