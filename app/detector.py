"""Explainable detection engine. The three SRS signals always explain the decision."""
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from sqlalchemy import func
from sqlalchemy.orm import Session
from .config import settings
from .models import Application


HARD_RULE_SCORE = 100.0


def similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, left.lower().strip(), right.lower().strip()).ratio()


def analyse_submission(db: Session, full_name: str, email: str, ip_address: str) -> tuple[float, list[str]]:
    now = datetime.utcnow()
    minute_ago = now - timedelta(seconds=settings.rapid_submission_window_seconds)
    five_minutes_ago = now - timedelta(seconds=settings.flood_window_seconds)

    ip_count = db.scalar(db.query(func.count(Application.id)).filter(Application.ip_address == ip_address, Application.submitted_at >= minute_ago).statement) or 0
    all_recent = db.scalar(db.query(func.count(Application.id)).filter(Application.submitted_at >= five_minutes_ago).statement) or 0
    # The SRS baseline is 500-1000 records; inspect that whole linked set so a
    # near-identical name is found even when its email/IP has been changed.
    candidates = db.query(Application).limit(1000).all()
    best_name_similarity = max((similarity(full_name, x.full_name) for x in candidates), default=0.0)
    exact_email = any(x.email.lower() == email.lower() for x in candidates)
    duplicate_signal = 1.0 if exact_email or best_name_similarity >= 0.90 else 0.0
    ip_signal = min(ip_count / settings.rapid_submission_limit, 1.0)
    velocity_signal = 1.0 if all_recent + 1 > settings.flood_batch_limit else min((all_recent + 1) / settings.flood_batch_limit, 1.0)

    # REQ-4: IP 40%, duplicate name/email 30%, velocity 30%.
    score = round(min(100.0, (ip_signal * 40 + duplicate_signal * 30 + velocity_signal * 30)), 2)
    # Hard rule: the weighted sum alone can never pass 70 without a flood, which would
    # make "block" unreachable. Two independent attack signals together (IP over its
    # limit AND a duplicate) are decisive, so the score is raised to the maximum.
    hard_rule_hit = ip_count >= settings.rapid_submission_limit and duplicate_signal == 1.0
    if hard_rule_hit:
        score = HARD_RULE_SCORE
    reasons: list[str] = []
    if hard_rule_hit:
        reasons.append("Hard rule: IP over its rate limit AND duplicate name/email -> block")
    if ip_count >= settings.rapid_submission_limit:
        reasons.append(f"IP submitted {ip_count} times in the last minute (limit {settings.rapid_submission_limit})")
    if exact_email:
        reasons.append("Email exactly matches an existing application")
    elif best_name_similarity >= 0.90:
        reasons.append(f"Name is {best_name_similarity:.0%} similar to an existing application")
    if all_recent + 1 > settings.flood_batch_limit:
        reasons.append(f"Flood threshold exceeded: {all_recent + 1} submissions in five minutes")
    if not reasons:
        reasons.append("No duplicate, rapid-IP, or flood indicators detected")
    return score, reasons


def choose_action(score: float) -> str:
    if score > settings.high_risk_threshold:
        return "block"
    if score >= settings.captcha_threshold:
        return "captcha"
    return "allow"
