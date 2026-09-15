from datetime import datetime
from typing import Literal
from pydantic import BaseModel, EmailStr, Field


class SubmissionIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    ip_address: str = Field(min_length=3, max_length=64)
    payload: dict = Field(default_factory=dict)


class DecisionOut(BaseModel):
    activity_id: int
    risk_score: float
    action: Literal["allow", "captcha", "block"]
    reasons: list[str]
    created_at: datetime


class OverrideIn(BaseModel):
    action: Literal["allow", "captcha", "block"]
    note: str = Field(min_length=3, max_length=1000)


class LoginIn(BaseModel):
    username: str
    password: str

