"""T4(c): HMAC-signed judge participation records.

The signature covers the fields the public verify route returns plus the
record id and its audit-chain anchor (audit_seq, audit_hash), so a record whose stored fields are edited (or whose key is rotated) verifies as
signature_valid=false. Verification is SERVER-MEDIATED: only this server holds
the key, so a third party has to ask this server; nothing here is a portable,
offline-verifiable credential (that would need an asymmetric signature).
"""
import hashlib
import hmac
import json

from . import config, models
from .windows import _as_utc_aware


def issued_iso(dt) -> str:
    return _as_utc_aware(dt).isoformat()


def canonical(rec: models.JudgeRecord) -> bytes:
    return json.dumps(
        {
            "id": rec.id,
            "judge_name": rec.judge_name,
            "event_name": rec.event_name,
            "reviews_completed": rec.reviews_completed,
            "issued_at": issued_iso(rec.issued_at),
            "audit_seq": rec.audit_seq,
            "audit_hash": rec.audit_hash,
        },
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def sign(rec: models.JudgeRecord) -> str:
    return hmac.new(config.RECORD_SIGNING_KEY.encode("utf-8"), canonical(rec), hashlib.sha256).hexdigest()


def signature_valid(rec: models.JudgeRecord) -> bool:
    return hmac.compare_digest(sign(rec), rec.signature)
