from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from core.database import get_db
from core.redis_client import get_redis
import redis

router = APIRouter(
    tags=["Status"]
)

@router.get("/status", status_code=status.HTTP_200_OK)
def check_health(db: Session = Depends(get_db), 
                 redis_client: redis.Redis = Depends(get_redis)):
    """
    Performs a health check on the API and its dependencies.
    """
    try:
        # 1. Check database connection
        db.execute('SELECT 1')
        # 2. Check Redis connection
        redis_client.ping()

        return {"status": "ok", "database": "connected", "redis": "connected"}
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                    "status": "error", 
                    "message": "A critical dependency is down.", 
                    "error_details": str(e)
                    }
        )
