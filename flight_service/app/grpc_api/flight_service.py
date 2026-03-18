from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import grpc
from google.protobuf.timestamp_pb2 import Timestamp
from sqlalchemy import select

from app.cache import (
    get_cached_flight,
    get_cached_search,
    invalidate_flight_cache,
    invalidate_search_cache,
    set_cached_flight,
    set_cached_search,
)
from app.db.models.flight import Flight, FlightStatus
from app.db.models.seat_reservation import ReservationStatus, SeatReservation
from app.db.session import SessionLocal
from shared.generated.flight.v1 import flight_service_pb2, flight_service_pb2_grpc


class FlightGrpcService(flight_service_pb2_grpc.FlightServiceServicer):
    def SearchFlights(self, request, context):
        departure_date = None
        if request.HasField("departure_date"):
            departure_date = request.departure_date.ToDatetime().date()

        cached = get_cached_search(
            request.origin_iata,
            request.destination_iata,
            departure_date,
        )
        if cached is not None:
            return flight_service_pb2.SearchFlightsResponse(
                flights=[self._map_flight_dict_to_proto(item) for item in cached]
            )

        with SessionLocal() as db:
            stmt = select(Flight).where(
                Flight.origin_iata == request.origin_iata.upper(),
                Flight.destination_iata == request.destination_iata.upper(),
                Flight.status == FlightStatus.SCHEDULED,
            )

            if departure_date is not None:
                stmt = stmt.where(Flight.flight_date == departure_date)

            flights = db.execute(stmt.order_by(Flight.departure_at)).scalars().all()
            set_cached_search(
                request.origin_iata,
                request.destination_iata,
                departure_date,
                flights,
            )

            return flight_service_pb2.SearchFlightsResponse(
                flights=[self._map_flight_to_proto(flight) for flight in flights]
            )

    def GetFlight(self, request, context):
        flight_id = self._parse_uuid(request.flight_id, "flight_id", context)

        cached = get_cached_flight(flight_id)
        if cached is not None:
            return flight_service_pb2.GetFlightResponse(
                flight=self._map_flight_dict_to_proto(cached)
            )

        with SessionLocal() as db:
            flight = db.get(Flight, flight_id)

            if not flight:
                context.abort(grpc.StatusCode.NOT_FOUND, "Flight not found")

            set_cached_flight(flight)

            return flight_service_pb2.GetFlightResponse(
                flight=self._map_flight_to_proto(flight)
            )

    def ReserveSeats(self, request, context):
        if request.seat_count <= 0:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "seat_count must be > 0")

        flight_id = self._parse_uuid(request.flight_id, "flight_id", context)
        booking_id = self._parse_uuid(request.booking_id, "booking_id", context)

        with SessionLocal() as db:
            existing_reservation = db.execute(
                select(SeatReservation).where(SeatReservation.booking_id == booking_id)
            ).scalar_one_or_none()

            if existing_reservation:
                if (
                    existing_reservation.flight_id == flight_id
                    and existing_reservation.seat_count == request.seat_count
                    and existing_reservation.status == ReservationStatus.ACTIVE
                ):
                    return flight_service_pb2.ReserveSeatsResponse(
                        reservation=self._map_reservation_to_proto(existing_reservation)
                    )

                context.abort(
                    grpc.StatusCode.ALREADY_EXISTS,
                    "Reservation for this booking_id already exists",
                )

            flight = db.execute(
                select(Flight).where(Flight.id == flight_id).with_for_update()
            ).scalar_one_or_none()

            if not flight:
                context.abort(grpc.StatusCode.NOT_FOUND, "Flight not found")

            if flight.status != FlightStatus.SCHEDULED:
                context.abort(
                    grpc.StatusCode.FAILED_PRECONDITION,
                    "Flight is not available for reservation",
                )

            if flight.available_seats < request.seat_count:
                context.abort(
                    grpc.StatusCode.RESOURCE_EXHAUSTED,
                    "Not enough available seats",
                )

            flight.available_seats -= request.seat_count

            reservation = SeatReservation(
                booking_id=booking_id,
                flight_id=flight.id,
                seat_count=request.seat_count,
                status=ReservationStatus.ACTIVE,
            )

            db.add(reservation)
            db.commit()
            db.refresh(reservation)

            invalidate_flight_cache(flight.id)
            invalidate_search_cache()

            return flight_service_pb2.ReserveSeatsResponse(
                reservation=self._map_reservation_to_proto(reservation)
            )

    def ReleaseReservation(self, request, context):
        booking_id = self._parse_uuid(request.booking_id, "booking_id", context)

        with SessionLocal() as db:
            reservation = db.execute(
                select(SeatReservation).where(
                    SeatReservation.booking_id == booking_id,
                    SeatReservation.status == ReservationStatus.ACTIVE,
                )
            ).scalar_one_or_none()

            if not reservation:
                context.abort(grpc.StatusCode.NOT_FOUND, "Active reservation not found")

            flight = db.execute(
                select(Flight).where(Flight.id == reservation.flight_id).with_for_update()
            ).scalar_one_or_none()

            if not flight:
                context.abort(grpc.StatusCode.NOT_FOUND, "Flight not found")

            flight.available_seats += reservation.seat_count
            reservation.status = ReservationStatus.RELEASED

            db.commit()
            db.refresh(reservation)

            invalidate_flight_cache(flight.id)
            invalidate_search_cache()

            return flight_service_pb2.ReleaseReservationResponse(
                reservation=self._map_reservation_to_proto(reservation)
            )

    @staticmethod
    def _parse_uuid(value: str, field_name: str, context) -> UUID:
        try:
            return UUID(value)
        except ValueError:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                f"{field_name} must be a valid UUID",
            )

    @staticmethod
    def _to_timestamp(value):
        timestamp = Timestamp()
        timestamp.FromDatetime(value)
        return timestamp

    @staticmethod
    def _to_amount_minor(value: Decimal) -> int:
        return int(value * Decimal("100"))

    @classmethod
    def _build_flight_proto(
        cls,
        *,
        id,
        flight_number,
        airline_code,
        origin_iata,
        destination_iata,
        departure_at,
        arrival_at,
        total_seats,
        available_seats,
        price,
        currency,
        status,
        created_at,
        updated_at,
    ) -> flight_service_pb2.Flight:
        return flight_service_pb2.Flight(
            id=str(id),
            flight_number=flight_number,
            airline_code=airline_code,
            origin_iata=origin_iata,
            destination_iata=destination_iata,
            departure_at=cls._to_timestamp(departure_at),
            arrival_at=cls._to_timestamp(arrival_at),
            total_seats=total_seats,
            available_seats=available_seats,
            price=flight_service_pb2.Money(
                amount_minor=cls._to_amount_minor(price),
                currency=currency,
            ),
            status=getattr(
                flight_service_pb2,
                f"FLIGHT_STATUS_{status}",
            ),
            created_at=cls._to_timestamp(created_at),
            updated_at=cls._to_timestamp(updated_at),
        )

    @classmethod
    def _map_flight_to_proto(cls, flight: Flight) -> flight_service_pb2.Flight:
        return cls._build_flight_proto(
            id=flight.id,
            flight_number=flight.flight_number,
            airline_code=flight.airline_code,
            origin_iata=flight.origin_iata,
            destination_iata=flight.destination_iata,
            departure_at=flight.departure_at,
            arrival_at=flight.arrival_at,
            total_seats=flight.total_seats,
            available_seats=flight.available_seats,
            price=flight.price,
            currency=flight.currency,
            status=flight.status.value,
            created_at=flight.created_at,
            updated_at=flight.updated_at,
        )

    @classmethod
    def _map_flight_dict_to_proto(cls, flight: dict) -> flight_service_pb2.Flight:
        return cls._build_flight_proto(
            id=flight["id"],
            flight_number=flight["flight_number"],
            airline_code=flight["airline_code"],
            origin_iata=flight["origin_iata"],
            destination_iata=flight["destination_iata"],
            departure_at=flight["departure_at"],
            arrival_at=flight["arrival_at"],
            total_seats=flight["total_seats"],
            available_seats=flight["available_seats"],
            price=flight["price"],
            currency=flight["currency"],
            status=flight["status"],
            created_at=flight["created_at"],
            updated_at=flight["updated_at"],
        )

    @classmethod
    def _map_reservation_to_proto(
        cls,
        reservation: SeatReservation,
    ) -> flight_service_pb2.SeatReservation:
        return flight_service_pb2.SeatReservation(
            id=str(reservation.id),
            booking_id=str(reservation.booking_id),
            flight_id=str(reservation.flight_id),
            seat_count=reservation.seat_count,
            status=getattr(
                flight_service_pb2,
                f"RESERVATION_STATUS_{reservation.status.value}",
            ),
            created_at=cls._to_timestamp(reservation.created_at),
            updated_at=cls._to_timestamp(reservation.updated_at),
        )