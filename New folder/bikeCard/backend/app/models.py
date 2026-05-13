from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, ForeignKey, 
    Numeric, Text, Enum as SQLEnum, Index, text
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import TSTZRANGE
import enum
from app.database import Base


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    DENTIST = "dentist"
    HYGIENIST = "hygienist"
    RECEPTIONIST = "receptionist"


class AppointmentStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    appointments_as_staff = relationship("Appointment", back_populates="staff", foreign_keys="Appointment.staff_id")
    audit_logs = relationship("AuditLog", back_populates="user")


class Patient(Base):
    __tablename__ = "patients"
    
    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=True, index=True)
    phone = Column(String(20), nullable=False)
    date_of_birth = Column(DateTime, nullable=True)
    address = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    appointments = relationship("Appointment", back_populates="patient")


class Resource(Base):
    __tablename__ = "resources"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    resource_type = Column(String(100), nullable=False)  # e.g., "chair", "room", "equipment"
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    appointments = relationship("Appointment", back_populates="resource")


class ProcedureType(Base):
    __tablename__ = "procedure_types"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True)
    code = Column(String(50), nullable=True, unique=True)
    description = Column(Text, nullable=True)
    default_duration_minutes = Column(Integer, nullable=False)  # Default duration in minutes
    default_price = Column(Numeric(10, 2), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    appointments = relationship("Appointment", back_populates="procedure_type")


class Appointment(Base):
    __tablename__ = "appointments"
    
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    staff_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    resource_id = Column(Integer, ForeignKey("resources.id", ondelete="RESTRICT"), nullable=True, index=True)
    procedure_type_id = Column(Integer, ForeignKey("procedure_types.id", ondelete="RESTRICT"), nullable=False)
    
    # Time range using PostgreSQL tstzrange
    time_range = Column(TSTZRANGE, nullable=False)
    
    status = Column(SQLEnum(AppointmentStatus), default=AppointmentStatus.SCHEDULED, nullable=False)
    notes = Column(Text, nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    patient = relationship("Patient", back_populates="appointments")
    staff = relationship("User", back_populates="appointments_as_staff", foreign_keys=[staff_id])
    resource = relationship("Resource", back_populates="appointments")
    procedure_type = relationship("ProcedureType", back_populates="appointments")
    audit_logs = relationship("AuditLog", back_populates="appointment")
    
    # Indexes for performance
    __table_args__ = (
        Index('ix_appointments_time_range', 'time_range', postgresql_using='gist'),
        Index('ix_appointments_status', 'status'),
        # EXCLUSION constraint to prevent double-booking of staff
        # Syntax: EXCLUDE USING gist (staff_id WITH =, time_range WITH &&)
        # This prevents overlapping time_range for the same staff_id
        Index(
            'exclude_staff_overlap',
            'staff_id',
            'time_range',
            postgresql_using='gist',
            postgresql_with={'staff_id': '=', 'time_range': '&&'},
            postgresql_where=text("status NOT IN ('cancelled', 'no_show')")
        ),
        # EXCLUSION constraint to prevent double-booking of resources
        Index(
            'exclude_resource_overlap',
            'resource_id',
            'time_range',
            postgresql_using='gist',
            postgresql_with={'resource_id': '=', 'time_range': '&&'},
            postgresql_where=text("status NOT IN ('cancelled', 'no_show') AND resource_id IS NOT NULL")
        ),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id", ondelete="CASCADE"), nullable=True, index=True)
    action = Column(String(100), nullable=False)  # e.g., "created", "updated", "cancelled"
    details = Column(Text, nullable=True)  # JSON string with change details
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")
    appointment = relationship("Appointment", back_populates="audit_logs")
