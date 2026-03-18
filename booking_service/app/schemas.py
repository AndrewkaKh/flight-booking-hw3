from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class MoneyResponse(BaseModel):
    amount_minor: int
    currency: str


class FlightResponse(BaseModel):
    id: UUID
    flight_number: str
    airline_code: str
    origin_iata: str
    destination_iata: str
    departure_at: datetime
    arrival_at: datetime
    total_seats: int
    available_seats: int
    price: MoneyResponse
    status: str
    created_at: datetime
    updated_at: datetime


class CreateBookingRequest(BaseModel):
    user_id: UUID
    flight_id: UUID
    passenger_name: str
    passenger_email: str
    seat_count: int


class BookingResponse(BaseModel):
    id: UUID
    user_id: UUID
    flight_id: UUID
    passenger_name: str
    passenger_email: str
    seat_count: int
    total_price_minor: int
    currency: str
    status: str
    created_at: datetime
    updated_at: datetime