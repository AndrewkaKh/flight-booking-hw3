import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import CheckConstraint, Date, DateTime, Enum as SqlEnum, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class FlightStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    DEPARTED = "DEPARTED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class Flight(Base):
    __tablename__ = "flights"

    __table_args__ = (
        UniqueConstraint("flight_number", "flight_date", name="uq_flight_number_date"),
        CheckConstraint("total_seats > 0", name="chk_flight_total_seats_positive"),
        CheckConstraint("available_seats >= 0", name="chk_flight_available_seats_non_negative"),
        CheckConstraint("available_seats <= total_seats", name="chk_flight_available_seats_le_total"),
        CheckConstraint("price > 0", name="chk_flight_price_positive"),
        CheckConstraint("origin_iata <> destination_iata", name="chk_flight_route_not_same"),
        CheckConstraint("arrival_at > departure_at", name="chk_flight_arrival_after_departure"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    flight_number: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    airline_code: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )

    origin_iata: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        index=True,
    )

    destination_iata: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        index=True,
    )

    flight_date: Mapped[datetime.date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    departure_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    arrival_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    total_seats: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    available_seats: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="RUB",
    )

    status: Mapped[FlightStatus] = mapped_column(
        SqlEnum(FlightStatus, name="flight_status"),
        nullable=False,
        default=FlightStatus.SCHEDULED,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    seat_reservations: Mapped[list["SeatReservation"]] = relationship(
        "SeatReservation",
        back_populates="flight",
        cascade="all, delete-orphan",
    )