from __future__ import annotations

from typing import Callable

import grpc

from app.core.settings import settings


class ApiKeyAuthInterceptor(grpc.ServerInterceptor):
    def intercept_service(self, continuation: Callable, handler_call_details):
        metadata = dict(handler_call_details.invocation_metadata or ())
        provided_key = metadata.get("x-api-key")

        if provided_key != settings.service_api_key:
            def abort_handler(request, context):
                context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid or missing API key")

            rpc_handler = continuation(handler_call_details)

            if rpc_handler is None:
                return grpc.unary_unary_rpc_method_handler(abort_handler)

            if rpc_handler.unary_unary:
                return grpc.unary_unary_rpc_method_handler(
                    abort_handler,
                    request_deserializer=rpc_handler.request_deserializer,
                    response_serializer=rpc_handler.response_serializer,
                )

            if rpc_handler.unary_stream:
                return grpc.unary_stream_rpc_method_handler(
                    abort_handler,
                    request_deserializer=rpc_handler.request_deserializer,
                    response_serializer=rpc_handler.response_serializer,
                )

            if rpc_handler.stream_unary:
                return grpc.stream_unary_rpc_method_handler(
                    abort_handler,
                    request_deserializer=rpc_handler.request_deserializer,
                    response_serializer=rpc_handler.response_serializer,
                )

            if rpc_handler.stream_stream:
                return grpc.stream_stream_rpc_method_handler(
                    abort_handler,
                    request_deserializer=rpc_handler.request_deserializer,
                    response_serializer=rpc_handler.response_serializer,
                )

            return grpc.unary_unary_rpc_method_handler(abort_handler)

        return continuation(handler_call_details)