"""ORM models.

Importing this package registers every model on ``Base.metadata`` — required by
Alembic autogeneration and by ``create_all`` in the test fixtures.
"""

from app.models.appointment import Appointment
from app.models.appointment_type import AppointmentType
from app.models.audit import AuditLog
from app.models.decision import SchedulingDecision
from app.models.displacement import AppointmentDisplacement
from app.models.doctor import DoctorProfile
from app.models.patient import Patient
from app.models.shift import Shift
from app.models.triage import TriageAssessment
from app.models.user import User

__all__ = [
    "Appointment",
    "AppointmentDisplacement",
    "AppointmentType",
    "AuditLog",
    "DoctorProfile",
    "Patient",
    "SchedulingDecision",
    "Shift",
    "TriageAssessment",
    "User",
]
