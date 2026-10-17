import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import products, pages, payments, auth, admin, profile

load_dotenv()

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "http://127.0.0.1:8000,http://localhost:8000",
    ).split(",")
    if origin.strip()
]

app = FastAPI(title="PriceWatch Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(pages.router)
app.include_router(products.router)
app.include_router(payments.router)
app.include_router(profile.router)

@app.on_event("startup")
def startup_event():
    print("✅ Application started")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}