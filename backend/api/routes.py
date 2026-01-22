# api endpoints
# GET / snapshot
from fastapi import APIRouter
from backend.services.snapshot_service import SnapshotService
from backend.adapters.bikes_adapter import BikeAdapter

router = APIRouter()
snapshot_service = SnapshotService(adapters=[BikeAdapter()])


# router.get("/snapshot")
def get_snapshot():
    return snapshot_service.build_snapshot()
