# ER Diagram

```mermaid
erDiagram
    FLIGHTS {
        UUID id PK
        VARCHAR flight_number
        VARCHAR airline_code
        VARCHAR origin_iata
        VARCHAR destination_iata
        DATE flight_date
        TIMESTAMPTZ departure_at
        TIMESTAMPTZ arrival_at
        INT total_seats
        INT available_seats
        BIGINT price_amount_minor
        VARCHAR price_currency
        VARCHAR status
        TIMESTAMPTZ created_at
        TIMESTAMPTZ updated_at
    }

    SEAT_RESERVATIONS {
        UUID id PK
        UUID booking_id UK
        UUID flight_id FK
        INT seat_count
        VARCHAR status
        TIMESTAMPTZ created_at
        TIMESTAMPTZ updated_at
    }

    BOOKINGS {
        UUID id PK
        UUID user_id
        UUID flight_id
        VARCHAR passenger_name
        VARCHAR passenger_email
        INT seat_count
        BIGINT total_price_minor
        VARCHAR currency
        VARCHAR status
        TIMESTAMPTZ created_at
        TIMESTAMPTZ updated_at
    }

    FLIGHTS ||--o{ SEAT_RESERVATIONS : by_flight_id
```

## Constraints

### FLIGHTS
- `UNIQUE (flight_number, flight_date)`
- `CHECK (total_seats > 0)`
- `CHECK (available_seats >= 0)`
- `CHECK (available_seats <= total_seats)`
- `CHECK (price_amount_minor > 0)`
- `CHECK (origin_iata <> destination_iata)`
- `CHECK (arrival_at > departure_at)`

### SEAT_RESERVATIONS
- `UNIQUE (booking_id)`
- `FOREIGN KEY (flight_id) REFERENCES flights(id)`
- `CHECK (seat_count > 0)`

### BOOKINGS
- `CHECK (seat_count > 0)`
- `CHECK (total_price_minor > 0)`

## Notes
- `SEAT_RESERVATIONS.booking_id` — логическая межсервисная ссылка на `BOOKINGS.id`
- физический `FOREIGN KEY` между `BOOKINGS` и `SEAT_RESERVATIONS` не используется, так как это разные БД