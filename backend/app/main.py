from fastapi import FastAPI

app = FastAPI(title="Open Social Scheduler")

@app.get("/health")
def health():
    return {"status": "ok"}
