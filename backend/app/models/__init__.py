"""CareerMail AI — ORM Models."""

from app.models.user import User
from app.models.email_account import EmailAccount
from app.models.email_message import EmailMessage
from app.models.opportunity import Opportunity
from app.models.status_history import OpportunityStatusHistory
from app.models.opportunity_email import OpportunityEmail
from app.models.device import DeviceToken
from app.models.notification import NotificationLog

__all__ = [
    "User",
    "EmailAccount",
    "EmailMessage",
    "Opportunity",
    "OpportunityStatusHistory",
    "OpportunityEmail",
    "DeviceToken",
    "NotificationLog",
]

