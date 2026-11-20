from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect
)
from fastapi import UploadFile, File, Body
from openpyxl import load_workbook
from io import BytesIO
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel

import models
import schemas

from database import engine, get_db


# ==========================================
# FASTAPI APPLICATION
# ==========================================

app = FastAPI(title="Smart RFID Attendance API")


# ==========================================
# WEBSOCKET CONNECTION MANAGER
# ==========================================

class ConnectionManager:

    def __init__(self):
        self.active_connections = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):

        disconnected = []

        for connection in self.active_connections:
            try:
                await connection.send_json(message)

            except Exception:
                disconnected.append(connection)

        for connection in disconnected:
            self.disconnect(connection)


manager = ConnectionManager()

pending_rfid_registration = None

# ==========================================
# WEBSOCKET ENDPOINT
# ==========================================

@app.websocket("/ws/attendance")
async def attendance_websocket(websocket: WebSocket):

    await manager.connect(websocket)

    try:
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        manager.disconnect(websocket)

    except Exception:
        manager.disconnect(websocket)


# ==========================================
# CORS CONFIGURATION
# ==========================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================
# DATABASE INITIALIZATION
# ==========================================

models.Base.metadata.create_all(bind=engine)


# ==========================================
# HOME ROUTE
# ==========================================

@app.get("/")
def home():

    return {
        "message": "Smart RFID Attendance API is running"
    }


# ==========================================
# STUDENT REGISTRATION
# ==========================================

@app.post("/api/students/register")
def register_student(
    data: schemas.StudentCreate,
    db: Session = Depends(get_db)
):

    uid = data.uid.replace(" ", "").upper()
    roll = data.roll_number.strip().upper()

    if not uid:
        raise HTTPException(
            status_code=400,
            detail="Invalid RFID UID"
        )

    existing_roll = db.query(models.Student).filter(
        models.Student.roll_number == roll
    ).first()

    if existing_roll:
        raise HTTPException(
            status_code=409,
            detail="Roll number already registered"
        )

    existing_card = db.query(models.RFIDCard).filter(
        models.RFIDCard.uid == uid
    ).first()

    if existing_card:
        raise HTTPException(
            status_code=409,
            detail="RFID card already registered"
        )

    try:

        student = models.Student(
            name=data.name,
            roll_number=roll,
            department=data.department
        )

        db.add(student)
        db.flush()

        card = models.RFIDCard(
            uid=uid,
            student_id=student.id
        )

        db.add(card)

        db.commit()
        db.refresh(student)

        return {
            "success": True,
            "message": "Student registered successfully",
            "student_id": student.id,
            "name": student.name,
            "roll_number": student.roll_number,
            "uid": uid
        }

    except IntegrityError:

        db.rollback()

        raise HTTPException(
            status_code=409,
            detail="Student or RFID card already exists"
        )

    except Exception:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Unable to register student"
        )


@app.post("/api/students/import")
async def import_students(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # Validate file extension
    if not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=400,
            detail="Please upload an .xlsx Excel file"
        )

    try:
        contents = await file.read()

        workbook = load_workbook(
            filename=BytesIO(contents),
            read_only=True,
            data_only=True
        )

        sheet = workbook.active

        # Read headers
        headers = [
            str(cell.value).strip().lower()
            if cell.value is not None else ""
            for cell in sheet[1]
        ]

        required_columns = ["name", "roll number", "department"]

        missing_columns = [
            column for column in required_columns
            if column not in headers
        ]

        if missing_columns:
            raise HTTPException(
                status_code=400,
                detail=f"Missing Excel columns: {missing_columns}"
            )

        name_index = headers.index("name")
        roll_index = headers.index("roll number")
        department_index = headers.index("department")

        imported = []
        skipped = []

        for row_number, row in enumerate(
            sheet.iter_rows(min_row=2, values_only=True),
            start=2
        ):
            name = row[name_index]
            roll_number = row[roll_index]
            department = row[department_index]

            # Skip completely empty rows
            if not name and not roll_number and not department:
                continue

            if not name or not roll_number:
                skipped.append({
                    "row": row_number,
                    "reason": "Name or roll number is missing"
                })
                continue

            name = str(name).strip()
            roll_number = str(roll_number).strip().upper()

            department = (
                str(department).strip()
                if department is not None else None
            )

            if not name or not roll_number:
                skipped.append({
                    "row": row_number,
                    "reason": "Invalid name or roll number"
                })
                continue

            existing = db.query(models.Student).filter(
                models.Student.roll_number == roll_number
            ).first()

            if existing:
                skipped.append({
                    "row": row_number,
                    "roll_number": roll_number,
                    "reason": "Roll number already exists"
                })
                continue

            student = models.Student(
                name=name,
                roll_number=roll_number,
                department=department
            )

            db.add(student)

            imported.append({
                "name": name,
                "roll_number": roll_number
            })

        db.commit()
        workbook.close()

        return {
            "success": True,
            "imported_count": len(imported),
            "skipped_count": len(skipped),
            "imported_students": imported,
            "skipped_students": skipped,
            "message": "Student Excel import completed"
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Excel import failed: {str(e)}"
        )


@app.post("/api/rfid/assign")
def assign_rfid_card(
    student_id: int = Body(...),
    uid: str = Body(...),
    db: Session = Depends(get_db)
):
    # Normalize UID
    uid = uid.replace(" ", "").strip().upper()

    if not uid:
        raise HTTPException(
            status_code=400,
            detail="Invalid RFID UID"
        )

    # Find selected student
    student = db.query(models.Student).filter(
        models.Student.id == student_id
    ).first()

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Student not found"
        )

    # Check whether student already has an active card
    existing_student_card = db.query(models.RFIDCard).filter(
        models.RFIDCard.student_id == student_id,
        models.RFIDCard.is_active == True
    ).first()

    if existing_student_card:
        raise HTTPException(
            status_code=409,
            detail="This student already has an active RFID card"
        )

    # Check whether UID is already registered
    existing_uid = db.query(models.RFIDCard).filter(
        models.RFIDCard.uid == uid
    ).first()

    if existing_uid:
        raise HTTPException(
            status_code=409,
            detail="This RFID card has already been registered"
        )

    try:
        card = models.RFIDCard(
            uid=uid,
            student_id=student_id,
            is_active=True
        )

        db.add(card)
        db.commit()
        db.refresh(card)

        return {
            "success": True,
            "message": "RFID card assigned successfully",
            "student": {
                "id": student.id,
                "name": student.name,
                "roll_number": student.roll_number
            },
            "rfid": {
                "card_id": card.id,
                "uid": card.uid,
                "is_active": card.is_active
            }
        }

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="RFID card is already registered"
        )

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to assign RFID card"
        )

class RFIDRegistrationStart(BaseModel):
    student_id: int


class RFIDRegistrationScan(BaseModel):
    uid: str
    device_id: str


@app.post("/api/rfid/registration/start")
def start_rfid_registration(
    data: RFIDRegistrationStart,
    db: Session = Depends(get_db)
):
    global pending_rfid_registration

    student = db.query(models.Student).filter(
        models.Student.id == data.student_id
    ).first()

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Student not found"
        )

    existing_card = db.query(models.RFIDCard).filter(
        models.RFIDCard.student_id == student.id,
        models.RFIDCard.is_active == True
    ).first()

    if existing_card:
        raise HTTPException(
            status_code=409,
            detail="Student already has an active RFID card"
        )

    pending_rfid_registration = student.id

    return {
        "success": True,
        "message": "Waiting for RFID card scan",
        "student_id": student.id,
        "name": student.name,
        "roll_number": student.roll_number
    }


@app.get("/api/rfid/registration/pending")
def get_pending_rfid_registration():
    return {
        "pending": pending_rfid_registration is not None,
        "student_id": pending_rfid_registration
    }


@app.post("/api/rfid/registration/scan")
def register_scanned_rfid(
    data: RFIDRegistrationScan,
    db: Session = Depends(get_db)
):
    global pending_rfid_registration

    if pending_rfid_registration is None:
        return {
            "success": False,
            "message": "No pending RFID registration"
        }

    uid = data.uid.replace(" ", "").strip().upper()

    if not uid:
        raise HTTPException(
            status_code=400,
            detail="Invalid RFID UID"
        )

    student = db.query(models.Student).filter(
        models.Student.id == pending_rfid_registration
    ).first()

    if not student:
        pending_rfid_registration = None
        raise HTTPException(
            status_code=404,
            detail="Selected student no longer exists"
        )

    existing_card = db.query(models.RFIDCard).filter(
        models.RFIDCard.uid == uid
    ).first()

    if existing_card:
        return {
            "success": False,
            "message": "This RFID card is already registered"
        }

    existing_student_card = db.query(models.RFIDCard).filter(
        models.RFIDCard.student_id == student.id,
        models.RFIDCard.is_active == True
    ).first()

    if existing_student_card:
        pending_rfid_registration = None
        return {
            "success": False,
            "message": "Student already has an active RFID card"
        }

    try:
        card = models.RFIDCard(
            uid=uid,
            student_id=student.id,
            is_active=True
        )

        db.add(card)
        db.commit()
        db.refresh(card)

        result = {
            "success": True,
            "message": "RFID card registered successfully",
            "student": {
                "id": student.id,
                "name": student.name,
                "roll_number": student.roll_number
            },
            "uid": uid,
            "device_id": data.device_id
        }

        pending_rfid_registration = None

        return result

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="RFID card or student already registered"
        )

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to register RFID card"
        )


# ==========================================
# START ATTENDANCE SESSION
# ==========================================

@app.post("/api/sessions")
@app.post("/api/sessions/start")
def start_session(data: schemas.SessionCreate, db: Session = Depends(get_db)):
    subject = data.subject.strip()

    if not subject:
        raise HTTPException(
            status_code=400,
            detail="Subject cannot be empty"
        )

    try:
        # Deactivate previous active sessions
        db.query(models.AttendanceSession).filter(
            models.AttendanceSession.is_active == True
        ).update(
            {"is_active": False},
            synchronize_session=False
        )

        # Create new session
        session = models.AttendanceSession(
            subject=subject,
            is_active=True
        )

        db.add(session)
        db.flush()  # Generate session ID before committing

        # Get all currently registered students
        students = db.query(models.Student).all()

        # Enroll every student in this session
        for student in students:
            enrollment = models.SessionEnrollment(
                session_id=session.id,
                student_id=student.id
            )
            db.add(enrollment)

        # Commit session and enrollments together
        db.commit()
        db.refresh(session)

        return {
            "success": True,
            "session_id": session.id,
            "subject": session.subject,
            "is_active": session.is_active,
            "total_enrolled": len(students),
            "message": "Attendance session started successfully"
        }

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to start attendance session"
        )


# ==========================================
# END ATTENDANCE SESSION
# ==========================================

@app.post("/api/sessions/end")
def end_session(
    data: schemas.SessionEnd,
    db: Session = Depends(get_db)
):

    session = db.query(
        models.AttendanceSession
    ).filter(
        models.AttendanceSession.id == data.session_id
    ).first()

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Attendance session not found"
        )

    if not session.is_active:
        raise HTTPException(
            status_code=400,
            detail="Session is already inactive"
        )

    try:

        session.is_active = False

        db.commit()

        return {
            "success": True,
            "session_id": session.id,
            "subject": session.subject,
            "is_active": False,
            "message": "Attendance session ended successfully"
        }

    except Exception:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Unable to end attendance session"
        )


# ==========================================
# GET ACTIVE SESSION
# ==========================================

@app.get("/api/sessions/active")
def get_active_session(
    db: Session = Depends(get_db)
):

    session = db.query(
        models.AttendanceSession
    ).filter(
        models.AttendanceSession.is_active == True
    ).order_by(
        models.AttendanceSession.id.desc()
    ).first()

    if not session:
        return {
            "active": False,
            "message": "No active attendance session"
        }

    return {
        "active": True,
        "session_id": session.id,
        "subject": session.subject,
        "created_at": (
            session.created_at.isoformat()
            if session.created_at else None
        )
    }

@app.get("/api/sessions/{session_id}/report")
def get_session_report(
    session_id: int,
    db: Session = Depends(get_db)
):
    # Find the session
    session = db.query(models.AttendanceSession).filter(
        models.AttendanceSession.id == session_id
    ).first()

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Session not found"
        )

    # Get all students enrolled in this session
    enrollments = db.query(models.SessionEnrollment).filter(
        models.SessionEnrollment.session_id == session_id
    ).all()

    # Get attendance records for this session
    attendance_records = db.query(models.Attendance).filter(
        models.Attendance.session_id == session_id
    ).all()

    # Map attendance records by student ID
    attendance_map = {
        record.student_id: record
        for record in attendance_records
    }

    present_students = []
    absent_students = []

    for enrollment in enrollments:
        student = db.query(models.Student).filter(
            models.Student.id == enrollment.student_id
        ).first()

        if not student:
            continue

        attendance = attendance_map.get(student.id)

        student_data = {
            "student_id": student.id,
            "name": student.name,
            "roll_number": student.roll_number,
            "department": student.department
        }

        if attendance and attendance.status == "present":
            student_data["status"] = "present"
            student_data["timestamp"] = (
                attendance.timestamp.isoformat()
                if attendance.timestamp else None
            )
            present_students.append(student_data)
        else:
            student_data["status"] = "absent"
            student_data["timestamp"] = None
            absent_students.append(student_data)

    total_enrolled = len(present_students) + len(absent_students)
    total_present = len(present_students)
    total_absent = len(absent_students)

    attendance_percentage = (
        (total_present / total_enrolled) * 100
        if total_enrolled > 0 else 0
    )

    return {
        "success": True,
        "session": {
            "session_id": session.id,
            "subject": session.subject,
            "is_active": session.is_active,
            "created_at": (
                session.created_at.isoformat()
                if session.created_at else None
            )
        },
        "summary": {
            "total_enrolled": total_enrolled,
            "present": total_present,
            "absent": total_absent,
            "attendance_percentage": round(attendance_percentage, 2)
        },
        "present_students": present_students,
        "absent_students": absent_students
    }

@app.get("/api/sessions")
def get_all_sessions(db: Session = Depends(get_db)):
    sessions = db.query(models.AttendanceSession).order_by(
        models.AttendanceSession.created_at.desc()
    ).all()

    return [
        {
            "session_id": session.id,
            "subject": session.subject,
            "is_active": session.is_active,
            "created_at": (
                session.created_at.isoformat()
                if session.created_at else None
            )
        }
        for session in sessions
    ]
# ==========================================
# RFID ATTENDANCE
# ==========================================

@app.post("/api/attendance")
async def mark_attendance(
    data: schemas.AttendanceData,
    db: Session = Depends(get_db)
):

    uid = data.uid.replace(" ", "").upper()

    # Find RFID card

    card = db.query(models.RFIDCard).filter(
        models.RFIDCard.uid == uid,
        models.RFIDCard.is_active == True
    ).first()

    if not card:
        return {
            "success": False,
            "status": "unknown",
            "message": "Unknown or inactive RFID card"
        }

    # Find active session

    active_session = db.query(
        models.AttendanceSession
    ).filter(
        models.AttendanceSession.is_active == True
    ).order_by(
        models.AttendanceSession.id.desc()
    ).first()

    if not active_session:
        return {
            "success": False,
            "status": "no_session",
            "message": "No active attendance session"
        }

    # Find student

    student = db.query(models.Student).filter(
        models.Student.id == card.student_id
    ).first()

    if not student:
        return {
            "success": False,
            "status": "unknown",
            "message": "Student not found"
        }

    # Check duplicate attendance

    existing = db.query(models.Attendance).filter(
        models.Attendance.student_id == student.id,
        models.Attendance.session_id == active_session.id
    ).first()

    if existing:
        return {
            "success": False,
            "status": "duplicate",
            "name": student.name,
            "roll": student.roll_number,
            "message": "Attendance already marked"
        }

    # Create attendance record

    record = models.Attendance(
        student_id=student.id,
        session_id=active_session.id,
        device_id=data.device_id,
        status="present"
    )

    try:

        db.add(record)

        db.commit()
        db.refresh(record)

    except IntegrityError:

        db.rollback()

        return {
            "success": False,
            "status": "duplicate",
            "name": student.name,
            "roll": student.roll_number,
            "message": "Attendance already marked"
        }

    except Exception:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Unable to mark attendance"
        )

    # Broadcast attendance to connected clients

    await manager.broadcast({
        "type": "attendance_marked",
        "data": {
            "id": record.id,
            "name": student.name,
            "roll_number": student.roll_number,
            "session_id": active_session.id,
            "subject": active_session.subject,
            "device_id": record.device_id,
            "status": record.status,
            "timestamp": record.timestamp.isoformat()
        }
    })

    return {
        "success": True,
        "status": "present",
        "name": student.name,
        "roll": student.roll_number,
        "subject": active_session.subject,
        "message": "Attendance marked successfully",
        "timestamp": record.timestamp.isoformat()
    }


# ==========================================
# GET ALL STUDENTS
# ==========================================

@app.get("/api/students")
def get_students(db: Session = Depends(get_db)):
    students = db.query(models.Student).all()

    return [
        {
            "id": student.id,
            "name": student.name,
            "roll_number": student.roll_number,
            "department": student.department,
            "rfid_registered": any(
                card.is_active for card in student.cards
            ),
            "rfid_uid": next(
                (
                    card.uid for card in student.cards
                    if card.is_active
                ),
                None
            )
        }
        for student in students
    ]

# ==========================================
# GET ALL ATTENDANCE RECORDS
# ==========================================

@app.get("/api/attendance")
def get_attendance(
    db: Session = Depends(get_db)
):

    records = db.query(
        models.Attendance
    ).order_by(
        models.Attendance.id.desc()
    ).all()

    result = []

    for record in records:

        student = db.query(models.Student).filter(
            models.Student.id == record.student_id
        ).first()

        session = db.query(
            models.AttendanceSession
        ).filter(
            models.AttendanceSession.id == record.session_id
        ).first()

        if not student or not session:
            continue

        result.append({
            "id": record.id,
            "name": student.name,
            "roll_number": student.roll_number,
            "session_id": record.session_id,
            "subject": session.subject,
            "device_id": record.device_id,
            "status": record.status,
            "timestamp": record.timestamp.isoformat()
        })

    return result