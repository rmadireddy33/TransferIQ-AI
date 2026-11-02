from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import String
from sqlalchemy.types import TypeDecorator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """SQLite has no timezone-aware timestamp storage; preserve UTC explicitly."""
    impl = String(32)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Timestamp must be timezone aware")
        return value.astimezone(timezone.utc).isoformat(timespec="microseconds")

    def process_result_value(self, value, dialect):
        return datetime.fromisoformat(value) if value else None


class ExactQuantity(TypeDecorator):
    """Exact Decimal stored as TEXT; up to 18 integer and 8 fractional digits.

    SQLite NUMERIC affinity can coerce decimals to binary floats. Never use SQL
    arithmetic on this column; load Decimal values for deterministic calculations.
    """
    impl = String(28)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, (float, bool)):
            raise ValueError("Quantity must be Decimal, integer, or decimal string")
        try:
            number = Decimal(value)
            if not number.is_finite() or number < 0 or number >= Decimal("1e18"):
                raise ValueError("Quantity outside supported range")
            scaled = number.quantize(Decimal("0.00000001"))
            if scaled != number:
                raise ValueError("Quantity exceeds eight decimal places")
        except InvalidOperation as exc:
            raise ValueError("Invalid quantity") from exc
        return format(scaled, "f")

    def process_result_value(self, value, dialect):
        return Decimal(value) if value is not None else None
