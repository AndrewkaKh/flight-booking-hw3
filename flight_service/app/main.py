from __future__ import annotations

from concurrent import futures

import grpc

from app.core.settings import settings
from app.db.base import Base
from app.db.session import engine
from app.grpc_api.auth import ApiKeyAuthInterceptor
from app.grpc_api.flight_service import FlightGrpcService
from shared.generated.flight.v1 import flight_service_pb2_grpc


def serve() -> None:
    Base.metadata.create_all(bind=engine)

    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=10),
        interceptors=[ApiKeyAuthInterceptor()],
    )
    flight_service_pb2_grpc.add_FlightServiceServicer_to_server(
        FlightGrpcService(),
        server,
    )
    server.add_insecure_port(f"{settings.grpc_host}:{settings.grpc_port}")
    server.start()
    print(f"Flight Service gRPC listening on {settings.grpc_host}:{settings.grpc_port}")
    server.wait_for_termination()


if __name__ == "__main__":
    serve()