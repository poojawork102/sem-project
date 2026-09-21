from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SubmissionIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    ip_address: str = Field(min_length=3, max_length=64)
    payload: dict = Field(default_factory=dict)


class PortalApplicationIn(BaseModel):
    model_config = ConfigDict(extra="allow")

    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    phone: str = Field(min_length=7, max_length=32)
    program: str = Field(min_length=2, max_length=120)
    date_of_birth: str = Field(min_length=8, max_length=20)
    city: str = Field(min_length=2, max_length=100)
    statement: str = Field(min_length=20, max_length=2000)


class ApplicationStatusIn(BaseModel):
    reference_code: str
    email: EmailStr


class DecisionOut(BaseModel):
    activity_id: int
    risk_score: float
    ai_anomaly_score: float | None = None
    ai_status: str
    action: Literal["allow", "captcha", "block"]
    reasons: list[str]
    created_at: datetime


class PortalDecisionOut(DecisionOut):
    reference_code: str


class OverrideIn(BaseModel):
    action: Literal["allow", "captcha", "block"]
    note: str = Field(min_length=3, max_length=1000)


class LoginIn(BaseModel):
    username: str
    password: str


class ChatMessageIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[dict] = Field(default_factory=list)
