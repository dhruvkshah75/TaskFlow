from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.database import engine
from .routers import api_keys, auth, status, tasks, user

app = FastAPI()

origins = ["*"]

app .add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_keys.router)
app.include_router(user.router)
app.include_router(auth.router)
app.include_router(tasks.router)


@app.get("/")
def root():
    return {
        "Welcome to TaskFlow"
    }