from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import redis

from app.core.settings import settings


redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)


def flight_cache_key(flight_id: UUID | str) -> str:
    return f"flight:{flight_id}"


def search_cache_key(origin: str, destination: str, flight_date: date | None) -> str:
    suffix = flight_date.isoformat() if flight_date else "any"
    return f"search:{origin.upper()}:{destination.upper()}:{suffix}"


def serialize_flight(flight) -> str:
    payload = {
        "id": str(flight.id),
        "flight_number": flight.flight_number,
        "airline_code": flight.airline_code,
        "origin_iata": flight.origin_iata,
        "destination_iata": flight.destination_iata,
        "flight_date": flight.flight_date.isoformat(),
        "departure_at": flight.departure_at.isoformat(),
        "arrival_at": flight.arrival_at.isoformat(),
        "total_seats": flight.total_seats,
        "available_seats": flight.available_seats,
        "price": str(flight.price),
        "currency": flight.currency,
        "status": flight.status.value,
        "created_at": flight.created_at.isoformat(),
        "updated_at": flight.updated_at.isoformat(),
    }
    return json.dumps(payload)


def deserialize_flight(payload: str) -> dict:
    data = json.loads(payload)
    data["id"] = UUID(data["id"])
    data["flight_date"] = date.fromisoformat(data["flight_date"])
    data["departure_at"] = datetime.fromisoformat(data["departure_at"])
    data["arrival_at"] = datetime.fromisoformat(data["arrival_at"])
    data["price"] = Decimal(data["price"])
    data["created_at"] = datetime.fromisoformat(data["created_at"])
    data["updated_at"] = datetime.fromisoformat(data["updated_at"])
    return data


def serialize_flights(flights: list) -> str:
    return json.dumps([json.loads(serialize_flight(flight)) for flight in flights])


def deserialize_flights(payload: str) -> list[dict]:
    items = json.loads(payload)
    result = []
    for item in items:
        item["id"] = UUID(item["id"])
        item["flight_date"] = date.fromisoformat(item["flight_date"])
        item["departure_at"] = datetime.fromisoformat(item["departure_at"])
        item["arrival_at"] = datetime.fromisoformat(item["arrival_at"])
        item["price"] = Decimal(item["price"])
        item["created_at"] = datetime.fromisoformat(item["created_at"])
        item["updated_at"] = datetime.fromisoformat(item["updated_at"])
        result.append(item)
    return result


def get_cached_flight(flight_id: UUID | str) -> dict | None:
    key = flight_cache_key(flight_id)
    value = redis_client.get(key)
    if value is None:
        print(f"cache miss: {key}", flush=True)
        return None
    print(f"cache hit: {key}", flush=True)
    return deserialize_flight(value)


def set_cached_flight(flight, ttl_seconds: int | None = None) -> None:
    key = flight_cache_key(flight.id)
    ttl = ttl_seconds or settings.flight_cache_ttl_seconds
    redis_client.setex(key, ttl, serialize_flight(flight))


def get_cached_search(origin: str, destination: str, flight_date: date | None) -> list[dict] | None:
    key = search_cache_key(origin, destination, flight_date)
    value = redis_client.get(key)
    if value is None:
        print(f"cache miss: {key}", flush=True)
        return None
    print(f"cache hit: {key}", flush=True)
    return deserialize_flights(value)


def set_cached_search(origin: str, destination: str, flight_date: date | None, flights: list, ttl_seconds: int | None = None) -> None:
    key = search_cache_key(origin, destination, flight_date)
    ttl = ttl_seconds or settings.search_cache_ttl_seconds
    redis_client.setex(key, ttl, serialize_flights(flights))


def invalidate_flight_cache(flight_id: UUID | str) -> None:
    key = flight_cache_key(flight_id)
    redis_client.delete(key)
    print(f"cache invalidated: {key}", flush=True)


def invalidate_search_cache() -> None:
    keys = redis_client.keys("search:*")
    if keys:
        redis_client.delete(*keys)
    print("cache invalidated: search:*", flush=True)