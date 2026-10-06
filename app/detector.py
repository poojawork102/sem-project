"""Explainable detection engine. The three SRS signals always explain the decision."""
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from sqlalchemy import func
from sqlalchemy.orm import Session
from .config import settings
from .models import Action, Application


HARD_RULE_SCORE = 100.0
NAME_COMPARE_ROWS = 1000
NAME_SIMILARITY_THRESHOLD = 0.90


def similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, left.lower().strip(), right.lower().strip()).ratio()


def analyse_submission(db: Session, full_name: str, email: str, ip_address: str, at: datetime | None = None) -> tuple[float, list[str]]:
    now = at or datetime.utcnow()
    minute_ago = now - timedelta(seconds=settings.rapid_submission_window_seconds)
    five_minutes_ago = now - timedelta(seconds=settings.flood_window_seconds)

    ip_count = db.scalar(db.query(func.count(Application.id)).filter(Application.ip_address == ip_address, Application.submitted_at >= minute_ago).statement) or 0
    all_recent = db.scalar(db.query(func.count(Application.id)).filter(Application.submitted_at >= five_minutes_ago).statement) or 0
    # Exact email match is queried directly (lowercased), so it is found no matter how
    # old the row is. Name similarity is only compared against the most recent rows.
    exact_email = db.query(Application.id).filter(func.lower(Application.email) == email.lower()).first() is not None
    recent_names = db.query(Application.full_name).order_by(Application.submitted_at.desc()).limit(NAME_COMPARE_ROWS).all()
    best_name_similarity = max((similarity(full_name, row[0]) for row in recent_names), default=0.0)
    # A look-alike name on its own is not enough (Priya Patil / Priya Patel are two people).
    # It only counts as a duplicate when a second signal agrees: the same IP already
    # submitted in the last minute, or the system is under flood.
    flooding = all_recent + 1 > settings.flood_batch_limit
    similar_name = best_name_similarity >= NAME_SIMILARITY_THRESHOLD
    similar_name_counts = similar_name and (ip_count >= 1 or flooding)
    duplicate_signal = 1.0 if exact_email or similar_name_counts else 0.0
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
    elif similar_name_counts:
        reasons.append(f"Name is {best_name_similarity:.0%} similar to an existing application and the same IP/flood signal agrees")
    elif similar_name:
        reasons.append(f"Name is {best_name_similarity:.0%} similar to an existing application (not counted alone)")
    if flooding:
        reasons.append(f"Flood threshold exceeded: {all_recent + 1} submissions in five minutes")
    if not reasons:
        reasons.append("No duplicate, rapid-IP, or flood indicators detected")
    return score, reasons


def choose_action(score: float) -> str:
    if score > settings.high_risk_threshold:
        return Action.BLOCK.value
    if score >= settings.captcha_threshold:
        return Action.CAPTCHA.value
    return Action.ALLOW.value
