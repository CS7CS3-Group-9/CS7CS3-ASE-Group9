from fastapi import APIRouter

router = APIRouter()


@router.get("/api/hello")
async def hello_world():
    return {"message": "Hello World!"}
