
from pydantic import BaseModel, Field


class StudentCreate(BaseModel):
    name: str
    roll_number: str
    department: str
    uid: str


class SessionCreate(BaseModel):
    subject: str = Field(min_length=1, max_length=100)


class SessionEnd(BaseModel):
    session_id: int


class AttendanceData(BaseModel):
    uid: str = Field(min_length=1, max_length=32)
    device_id: str = Field(min_length=1, max_length=100)
