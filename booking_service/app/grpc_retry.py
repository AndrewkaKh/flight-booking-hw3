from __future__ import annotations

import time
from collections.abc import Callable

import grpc

from app.core.settings import settings


RETRYABLE_STATUS_CODES = {
    grpc.StatusCode.UNAVAILABLE,
    grpc.StatusCode.DEADLINE_EXCEEDED,
}


def call_with_retry(func: Callable):
    attempts = max(1, settings.grpc_retry_max_attempts)
    initial_backoff_ms = max(1, settings.grpc_retry_initial_backoff_ms)

    last_exc = None

    for attempt in range(1, attempts + 1):
        try:
            print(f"grpc retry attempt={attempt}", flush=True)
            return func()
        except grpc.RpcError as exc:
            last_exc = exc
            print(
                f"grpc retry error attempt={attempt} code={exc.code().name} details={exc.details()}",
                flush=True,
            )

            if exc.code() not in RETRYABLE_STATUS_CODES:
                raise

            if attempt >= attempts:
                raise

            backoff_seconds = (initial_backoff_ms * (2 ** (attempt - 1))) / 1000
            print(
                f"grpc retry sleeping={backoff_seconds}s next_attempt={attempt + 1}",
                flush=True,
            )
            time.sleep(backoff_seconds)

    if last_exc is not None:
        raise last_exc