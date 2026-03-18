from __future__ import annotations

from datetime import date, datetime, time, timezone

import grpc
from google.protobuf.timestamp_pb2 import Timestamp

from app.core.settings import settings
from app.grpc_retry import call_with_retry
from shared.generated.flight.v1 import flight_service_pb2, flight_service_pb2_grpc


class FlightServiceClient:
    def __init__(self) -> None:
        self._target = f"{settings.flight_service_host}:{settings.flight_service_port}"
        self._timeout = settings.grpc_timeout_seconds
        self._metadata = (("x-api-key", settings.flight_service_api_key),)

    def _make_stub(self):
        channel = grpc.insecure_channel(self._target)
        stub = flight_service_pb2_grpc.FlightServiceStub(channel)
        return channel, stub

    def search_flights(
        self,
        origin_iata: str,
        destination_iata: str,
        departure_date: date | None = None,
    ) -> list[flight_service_pb2.Flight]:
        request = flight_service_pb2.SearchFlightsRequest(
            origin_iata=origin_iata.upper(),
            destination_iata=destination_iata.upper(),
        )

        if departure_date is not None:
            timestamp = Timestamp()
            timestamp.FromDatetime(
                datetime.combine(departure_date, time.min, tzinfo=timezone.utc)
            )
            request.departure_date.CopyFrom(timestamp)

        channel, stub = self._make_stub()
        try:
            response = call_with_retry(
                lambda: stub.SearchFlights(
                    request,
                    timeout=self._timeout,
                    metadata=self._metadata,
                )
            )
            return list(response.flights)
        finally:
            channel.close()

    def get_flight(self, flight_id: str) -> flight_service_pb2.Flight:
        request = flight_service_pb2.GetFlightRequest(flight_id=flight_id)

        channel, stub = self._make_stub()
        try:
            response = call_with_retry(
                lambda: stub.GetFlight(
                    request,
                    timeout=self._timeout,
                    metadata=self._metadata,
                )
            )
            return response.flight
        finally:
            channel.close()

    def reserve_seats(
        self,
        booking_id: str,
        flight_id: str,
        seat_count: int,
    ) -> flight_service_pb2.SeatReservation:
        request = flight_service_pb2.ReserveSeatsRequest(
            booking_id=booking_id,
            flight_id=flight_id,
            seat_count=seat_count,
        )

        channel, stub = self._make_stub()
        try:
            response = call_with_retry(
                lambda: stub.ReserveSeats(
                    request,
                    timeout=self._timeout,
                    metadata=self._metadata,
                )
            )
            return response.reservation
        finally:
            channel.close()

    def release_reservation(self, booking_id: str) -> flight_service_pb2.SeatReservation:
        request = flight_service_pb2.ReleaseReservationRequest(booking_id=booking_id)

        channel, stub = self._make_stub()
        try:
            response = call_with_retry(
                lambda: stub.ReleaseReservation(
                    request,
                    timeout=self._timeout,
                    metadata=self._metadata,
                )
            )
            return response.reservation
        finally:
            channel.close()