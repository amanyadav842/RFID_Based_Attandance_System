
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    ForeignKey,
    UniqueConstraint
)

from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


# ==========================================
# STUDENT MODEL
# ==========================================

class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)

    roll_number = Column(
        String(30),
        unique=True,
        nullable=False
    )

    department = Column(String(50))

    cards = relationship(
        "RFIDCard",
        back_populates="student"
    )

    enrollments = relationship(
        "SessionEnrollment",
        back_populates="student"
    )


# ==========================================
# RFID CARD MODEL
# ==========================================

class RFIDCard(Base):
    __tablename__ = "rfid_cards"

    id = Column(Integer, primary_key=True, index=True)

    uid = Column(
        String(32),
        unique=True,
        nullable=False,
        index=True
    )

    student_id = Column(
        Integer,
        ForeignKey("students.id"),
        nullable=False
    )

    is_active = Column(Boolean, default=True)

    student = relationship(
        "Student",
        back_populates="cards"
    )


# ==========================================
# ATTENDANCE SESSION MODEL
# ==========================================

class AttendanceSession(Base):
    __tablename__ = "attendance_sessions"

    id = Column(Integer, primary_key=True, index=True)

    subject = Column(String(100), nullable=False)

    is_active = Column(Boolean, default=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    enrollments = relationship(
        "SessionEnrollment",
        back_populates="session"
    )


# ==========================================
# SESSION ENROLLMENT MODEL
# ==========================================

class SessionEnrollment(Base):
    __tablename__ = "session_enrollments"

    id = Column(Integer, primary_key=True, index=True)

    session_id = Column(
        Integer,
        ForeignKey("attendance_sessions.id"),
        nullable=False
    )

    student_id = Column(
        Integer,
        ForeignKey("students.id"),
        nullable=False
    )

    enrolled_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    session = relationship(
        "AttendanceSession",
        back_populates="enrollments"
    )

    student = relationship(
        "Student",
        back_populates="enrollments"
    )

    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "student_id",
            name="unique_session_student"
        ),
    )


# ==========================================
# ATTENDANCE MODEL
# ==========================================

class Attendance(Base):
    __tablename__ = "Attendance"

    id = Column(Integer, primary_key=True, index=True)

    student_id = Column(
        Integer,
        ForeignKey("students.id"),
        nullable=True
    )

    session_id = Column(
        Integer,
        ForeignKey("attendance_sessions.id"),
        nullable=False
    )

    device_id = Column(String(100))

    status = Column(String(20), default="present")

    timestamp = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "session_id",
            name="unique_student_session"
        ),
    )
