from sqlalchemy import JSON, Column, Integer, String
from sqlalchemy.orm import declarative_base
from wyzecam.api_models import WyzeCredential

Base = declarative_base()

CREDENTIAL_ID = 1


class Credential(Base):
    __tablename__ = "credential"

    id = Column(Integer, primary_key=True)
    access_token = Column(String)
    refresh_token = Column(String)
    user_id = Column(String)
    mfa_options = Column(JSON, nullable=True)
    mfa_details = Column(JSON, nullable=True)
    sms_session_id = Column(String, nullable=True)

    phone_id = Column(String)


class CredentialModel(WyzeCredential):
    id: int

    class Config:
        orm_mode = True
