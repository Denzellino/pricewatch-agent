from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_db
from app.routes import products, stores, pages, payments

app = FastAPI(title="PriceWatch Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pages.router)
app.include_router(stores.router)
app.include_router(products.router)
app.include_router(payments.router)

@app.on_event("startup")
def startup_event():
    init_db()
    print("✅ Database initialized")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}