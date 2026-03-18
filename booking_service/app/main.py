from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

import grpc
from fastapi import Depends, FastAPI, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models.booking import Booking, BookingStatus
from app.db.session import db_session
from app.flight_client import FlightServiceClient
from app.schemas import BookingResponse, CreateBookingRequest, FlightResponse, MoneyResponse
from shared.generated.flight.v1 import flight_service_pb2

app = FastAPI()
flight_client = FlightServiceClient()


def _raise_http_from_grpc(exc: grpc.RpcError) -> None:
    mapping = {
        grpc.StatusCode.INVALID_ARGUMENT: status.HTTP_400_BAD_REQUEST,
        grpc.StatusCode.NOT_FOUND: status.HTTP_404_NOT_FOUND,
        grpc.StatusCode.ALREADY_EXISTS: status.HTTP_409_CONFLICT,
        grpc.StatusCode.RESOURCE_EXHAUSTED: status.HTTP_409_CONFLICT,
        grpc.StatusCode.FAILED_PRECONDITION: status.HTTP_409_CONFLICT,
        grpc.StatusCode.UNAUTHENTICATED: status.HTTP_401_UNAUTHORIZED,
        grpc.StatusCode.UNAVAILABLE: status.HTTP_503_SERVICE_UNAVAILABLE,
        grpc.StatusCode.DEADLINE_EXCEEDED: status.HTTP_504_GATEWAY_TIMEOUT,
    }
    raise HTTPException(
        status_code=mapping.get(exc.code(), status.HTTP_502_BAD_GATEWAY),
        detail=exc.details() or "Flight service request failed",
    )


def _flight_status_to_str(value: int) -> str:
    return flight_service_pb2.FlightStatus.Name(value).removeprefix("FLIGHT_STATUS_")


def _proto_flight_to_response(flight) -> FlightResponse:
    return FlightResponse(
        id=UUID(flight.id),
        flight_number=flight.flight_number,
        airline_code=flight.airline_code,
        origin_iata=flight.origin_iata,
        destination_iata=flight.destination_iata,
        departure_at=flight.departure_at.ToDatetime(),
        arrival_at=flight.arrival_at.ToDatetime(),
        total_seats=flight.total_seats,
        available_seats=flight.available_seats,
        price=MoneyResponse(
            amount_minor=flight.price.amount_minor,
            currency=flight.price.currency,
        ),
        status=_flight_status_to_str(flight.status),
        created_at=flight.created_at.ToDatetime(),
        updated_at=flight.updated_at.ToDatetime(),
    )


def _booking_to_response(booking: Booking) -> BookingResponse:
    return BookingResponse(
        id=booking.id,
        user_id=booking.user_id,
        flight_id=booking.flight_id,
        passenger_name=booking.passenger_name,
        passenger_email=booking.passenger_email,
        seat_count=booking.seat_count,
        total_price_minor=booking.total_price_minor,
        currency=booking.currency,
        status=booking.status.value,
        created_at=booking.created_at,
        updated_at=booking.updated_at,
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/flights", response_model=list[FlightResponse])
def search_flights(
    origin: str = Query(..., min_length=3, max_length=3),
    destination: str = Query(..., min_length=3, max_length=3),
    date: date | None = Query(None),
):
    try:
        flights = flight_client.search_flights(origin, destination, date)
        return [_proto_flight_to_response(flight) for flight in flights]
    except grpc.RpcError as exc:
        _raise_http_from_grpc(exc)


@app.get("/flights/{flight_id}", response_model=FlightResponse)
def get_flight(flight_id: UUID):
    try:
        flight = flight_client.get_flight(str(flight_id))
        return _proto_flight_to_response(flight)
    except grpc.RpcError as exc:
        _raise_http_from_grpc(exc)


@app.post("/bookings", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
def create_booking(
    payload: CreateBookingRequest,
    db: Session = Depends(db_session),
):
    booking_id = uuid4()
    reserved = False

    try:
        flight = flight_client.get_flight(str(payload.flight_id))

        if _flight_status_to_str(flight.status) != "SCHEDULED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Flight is not available for booking",
            )

        flight_client.reserve_seats(
            booking_id=str(booking_id),
            flight_id=str(payload.flight_id),
            seat_count=payload.seat_count,
        )
        reserved = True

        booking = Booking(
            id=booking_id,
            user_id=payload.user_id,
            flight_id=payload.flight_id,
            passenger_name=payload.passenger_name,
            passenger_email=payload.passenger_email,
            seat_count=payload.seat_count,
            total_price_minor=flight.price.amount_minor * payload.seat_count,
            currency=flight.price.currency,
            status=BookingStatus.CONFIRMED,
        )

        db.add(booking)
        db.commit()
        db.refresh(booking)
        return _booking_to_response(booking)
    except grpc.RpcError as exc:
        db.rollback()
        _raise_http_from_grpc(exc)
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError:
        db.rollback()
        if reserved:
            try:
                flight_client.release_reservation(str(booking_id))
            except grpc.RpcError:
                pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create booking",
        )


@app.get("/bookings/{booking_id}", response_model=BookingResponse)
def get_booking(
    booking_id: UUID,
    db: Session = Depends(db_session),
):
    booking = db.get(Booking, booking_id)

    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        )

    return _booking_to_response(booking)


@app.post("/bookings/{booking_id}/cancel", response_model=BookingResponse)
def cancel_booking(
    booking_id: UUID,
    db: Session = Depends(db_session),
):
    booking = db.get(Booking, booking_id)

    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        )

    if booking.status != BookingStatus.CONFIRMED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Booking is not in CONFIRMED status",
        )

    try:
        flight_client.release_reservation(str(booking.id))
        booking.status = BookingStatus.CANCELLED
        db.commit()
        db.refresh(booking)
        return _booking_to_response(booking)
    except grpc.RpcError as exc:
        db.rollback()
        _raise_http_from_grpc(exc)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel booking",
        )


@app.get("/bookings", response_model=list[BookingResponse])
def list_bookings(
    user_id: UUID = Query(...),
    db: Session = Depends(db_session),
):
    bookings = (
        db.query(Booking)
        .filter(Booking.user_id == user_id)
        .order_by(Booking.created_at.desc())
        .all()
    )
    return [_booking_to_response(booking) for booking in bookings]