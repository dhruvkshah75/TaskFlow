from fastapi import HTTPException, status, APIRouter, Depends, Response, UploadFile, File, Query
from ..oauth2 import get_current_user
from core.database import get_db
from core import models
from sqlalchemy.orm import Session
from .. import schemas
from typing import List, Optional
from ..rate_limiter import user_rate_limiter
from ..utils import cache_task, check_cache_task
from core.redis_client import get_redis
import redis, logging, shutil, os
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

router = APIRouter(
    tags = ['tasks'],
    prefix = "/tasks"
)

# ============================ TASK RELATED CRUD OPERATRION ==========================

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=schemas.TaskResponse,
             dependencies = [Depends(user_rate_limiter)])
def create_task(task: schemas.TaskCreate, db: Session=Depends(get_db),
                current_user: models.User = Depends(get_current_user),
                redis_client: redis.Redis = Depends(get_redis)):
    """
    Creates a new task for the currently logged in user
    We also have to make sure that that the same task is not put up by the same user
    Can be done with the help of caching
    """
    task_data = check_cache_task(redis_client, task.title, current_user.id, task.payload)
    if task_data:
        logger.info(f"Cache HIT: Found a task with the same title:{task.title}")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"Task is already registered. Cannot register the same task again")
    else:
        logger.info(f"Cache MISS: Searching in the Database")
        task_data = db.query(models.Tasks).filter(
            models.Tasks.title == task.title,
            models.Tasks.payload == task.payload,
            models.Tasks.owner_id == current_user.id,
            models.Tasks.status != 'COMPLETED'
        ).first()

        if task_data:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"Task is already registered. Cannot register the same task again")
        
    schedule_time = task.scheduled_at  
    scheduled_for = datetime.now(timezone.utc) + timedelta(minutes=schedule_time)

    new_task = models.Tasks(
        **task.model_dump(exclude={"scheduled_at"}),   
        scheduled_at=scheduled_for,                    
        owner_id=current_user.id
    )
    # create the cache of the new task 
    cache_task(redis_client,{
        "title": task.title,
        "owner_id": current_user.id,
        "payload": task.payload
    })
    db.add(new_task)
    db.commit()
    db.refresh(new_task)

    return new_task



@router.get("/", response_model=List[schemas.TaskResponse], 
            dependencies = [Depends(user_rate_limiter)])
def get_all_tasks_by_user(db: Session=Depends(get_db),
                  current_user: dict = Depends(get_current_user), 
                  limit: int=10, skip: int=0, search: Optional[str] = "",
                  status: Optional[models.TaskStatus] = None):
    """
    Get all tasks for the current user.
    Can be filtered by title (search) and status, limit and offset also.
    """
    tasks_query = db.query(models.Tasks).filter(
        models.Tasks.owner_id == current_user.id
    )

    if search:
        tasks_query = tasks_query.filter(
            models.Tasks.title.ilike(f"%{search}%")
        )

    if status:
        tasks_query = tasks_query.filter(models.Tasks.status == status)

    tasks = tasks_query.limit(limit).offset(skip).all()
    return tasks
    

    
@router.get("/{task_id}", response_model=schemas.TaskResponse,
            dependencies = [Depends(user_rate_limiter)])
def get_a_task(task_id: int, db: Session=Depends(get_db),
                  current_user: models.User = Depends(get_current_user)):
    
    task = db.query(models.Tasks).filter(
        models.Tasks.id == task_id
    ).first()

    if task == None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Task with id: {task_id} not found")
    else:
        return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT, 
               dependencies = [Depends(user_rate_limiter)])
def delete_task(task_id: int, db: Session=Depends(get_db),
                current_user: models.User = Depends(get_current_user)):
    """
    Delete the task with this task id. 
    Only the user who created the task can delete this task with the id
    """

    task_user_query = db.query(models.Tasks).filter(
        models.Tasks.id == task_id
    )

    if task_user_query.first() == None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"The task with the id {task_id} not found"
        )
    else:
        task = task_user_query.filter(
            models.Tasks.owner_id == current_user.id
        ).first()

        if task == None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Not authorized to perform this action"
            )
        else:
            task_user_query.delete(synchronize_session=False)
            db.commit()
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        



# ==================================== UPLOADING A TASK FILE ===============================================

UPLOAD_DIR = "worker/tasks"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# file_name: Uses a Query parameter. The user will call it like ?file_name=p1
@router.post("/upload_file", status_code=status.HTTP_201_CREATED, 
             dependencies=[Depends(user_rate_limiter)])
async def upload_task_file(
    file_name: str = Query(..., description="The title that will be used to trigger this code"),
    file: UploadFile = File(...), 
    current_user: models.User = Depends(get_current_user)
):
    """
    Upload a Python script to be executed as a dynamic task.
    This endpoint allows users to upload custom business logic that the worker 
    cluster will execute. The uploaded file is stored in a shared volume.

    ### Task Script Protocol:
    The uploaded `.py` file **MUST** contain an `async def handler(payload: dict)` 
    function. This function is the entry point for the worker.

    **Example script:**
    ```python
    async def handler(payload):
        return {"result": f"Processed {payload.get('data')}"}
    ```
    ### Parameters:
    - **file_name**: The title/identifier. This name must be used as the `title` 
      when creating a task via `POST /tasks/`.
    - **file**: A `.py` file containing the task logic.
    ### Response:
    - **201 Created**: File successfully saved to the shared volume.
    - **400 Bad Request**: If the file extension is not `.py`.
    - **429 Too Many Requests**: If the user exceeds the rate limit.
    - **500 Internal Server Error**: If there is a filesystem or storage error.
    ### Cleanup:
    Note: In this FaaS model, the logic file is automatically deleted from 
    the server after the task has been successfully executed or has failed.
    """
    # Validation: Only allow Python files
    if not file.filename.endswith(".py"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Only .py files are allowed"
        )

    # Define the path: Use task_title as the unique filename
    # This ensures the worker knows exactly which file to look for by title
    file_path = os.path.join(UPLOAD_DIR, f"{file_name}.py")

    # Save the file to the shared volume
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Failed to save the task file"
        )

    return {"message": f"Logic for task '{file_name}' uploaded successfully"}






# ### 1. Using `curl` (Command Line)
# This is the most likely way a developer will test your system.
# * The `-H` flag sends your JWT token.
# * The `-F` flag (Form) tells curl to upload a file. The `@` symbol is crucial—it tells curl to look for a file on the local disk.

# curl -X POST "http://localhost:8000/tasks/upload_file?file_name=email_processor" \
#      -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
#      -F "file=@/path/to/your/local_script.py"


# ### 2. Using Python `requests`
# If the user is building their own client or a dashboard to interact with your platform, they would do this:

# import requests
# url = "http://localhost:8000/tasks/upload_file"
# params = {"file_name": "email_processor"}
# headers = {"Authorization": "Bearer YOUR_ACCESS_TOKEN"}

# # The dictionary key 'file' must match the variable name in your FastAPI function
# with open("local_script.py", "rb") as f:
#     files = {"file": f}
#     response = requests.post(url, params=params, headers=headers, files=files)

# print(response.json())



