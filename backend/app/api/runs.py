from fastapi import APIRouter ## make a router so we group all endpoints that start with run so if we call @router.get("/") the route is /runs/

router = APIRouter(prefix="/runs", tags=["runs"])
