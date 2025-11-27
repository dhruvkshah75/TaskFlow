from fastapi import HTTPException, status, APIRouter, Depends
from ..oauth2 import get_current_user
from core.database import get_db
from core import models
from sqlalchemy.orm import Session
from .. import schemas
from typing import List, Optional

router = APIRouter(
    tags = ['tasks'],
    prefix = "/tasks"
)

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=schemas.TaskResponse)
def create_task(task: schemas.TaskCreate, db: Session=Depends(get_db),
                current_user: dict = Depends(get_current_user)):
    """
    Creates a new task for the currently logged in user
    """
    new_task = models.Tasks(**task.model_dump(), owner_id = current_user.id)

    db.add(new_task)
    db.commit()
    db.refresh(new_task)

    return new_task



@router.get("/", response_model=List[schemas.TaskResponse])
def get_all_tasks(db: Session=Depends(get_db),
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
    

    
@router.get("/{task_id}", response_model=schemas.TaskResponse)
def get_a_task(task_id: int, db: Session=Depends(get_db),
                  current_user: dict = Depends(get_current_user)):
    
    task = db.query(models.Tasks).filter(
        models.Tasks.id == task_id
    ).first()

    if task == None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Task with id: {task_id} not found")
    else:
        return task


