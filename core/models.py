from .database import Base
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Enum as SQLAlchemyEnum, Text
from sqlalchemy.sql.expression import text
from sqlalchemy.sql.sqltypes import TIMESTAMP
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
import enum

class TaskStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class EventType(str, enum.Enum):
    WORKER_ASSIGNED = "WORKER_ASSIGNED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRIED = "RETRIED"
    CREATED = "CREATED"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, nullable=False)
    email = Column(String, nullable=False, unique=True)
    username = Column(String, nullable=False, unique=True)
    password = Column(String, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False,
                        server_default=text('now()'))
    

class Tasks(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, nullable=False)
    title = Column(String, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                      nullable=False)
    status = Column(SQLAlchemyEnum(TaskStatus), nullable=False,
                    default=TaskStatus.PENDING)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False,
                        server_default=text('now()'))
    worker_id = Column(String, nullable=True)
    # the defualt value is the time at which the task was created 
    updated_at = Column(TIMESTAMP(timezone=True), 
                        server_default=func.now(), onupdate=func.now())
    result = Column(JSONB, nullable=True)
    
    owner = relationship("User")
    events = relationship("TaskEvents", back_populates="task")


# A entry is added only once some action is done on the task 
class TaskEvents(Base):
    __tablename__ = "task_events"

    id = Column(Integer, primary_key=True, nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"),
                     nullable=False)
    event_type = Column(SQLAlchemyEnum(EventType), nullable=False)
    message = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True),
                        server_default=text('now()'), nullable=False)
    
    task = relationship("Tasks", back_populates="events")


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, nullable=False)
    key_hash = Column(String, nullable=False, unique=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                      nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'),
                        nullable=False)
    is_active = Column(Boolean, server_default='TRUE', nullable=False)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=True) 
    # if api key is not used for a long time then the key will be removed
    last_used_at = Column(TIMESTAMP(timezone=True), nullable=True)
    # Nullable means it can last forever

    owner = relationship("User")



class Webhook(Base):
    __tablename__ = "webhooks"

    id = Column(Integer, primary_key=True, nullable=False)
    event_type = Column(SQLAlchemyEnum(EventType), nullable=False)
    target_url = Column(String, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), 
                      nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, 
                        server_default=text('now()'))

    owner = relationship("User")