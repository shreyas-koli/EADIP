 
from fastapi import FastAPI

app = FastAPI(
    title="Enterprise Autonomous Data Intelligence Platform",
    version="1.0.0"
)

@app.get("/")
def root():
    return {
        "message": "Welcome to EADIP 🚀"
    }

@app.get("/health")
def health():
    return {
        "status": "healthy"
    }