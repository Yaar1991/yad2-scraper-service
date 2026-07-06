from typing import Any

from packages.data.db import Database
from packages.data.serialize import serialize_row, serialize_rows


class SubscriptionsRepository:
    def __init__(self, db: Database):
        self._db = db

    def list_alert_subscriptions(self, chat_id: str) -> list[dict[str, Any]]:
        with self._db.cursor() as cur:
            cur.execute(
                """
                SELECT id, chat_id, city, neighborhood, max_price, min_rooms, label,
                       notify_new, notify_price_drop, created_at
                FROM alert_subscriptions
                WHERE chat_id = %s
                ORDER BY created_at DESC
                """,
                (chat_id,),
            )
            rows = [dict(r) for r in cur.fetchall()]

        return [
            {
                "id": row["id"],
                "chat_id": row["chat_id"],
                "city": row["city"],
                "neighborhood": row["neighborhood"],
                "max_price": row["max_price"],
                "min_rooms": float(row["min_rooms"]) if row["min_rooms"] else None,
                "label": row["label"],
                "notify_new": row["notify_new"],
                "notify_price_drop": row["notify_price_drop"],
                "created_at": serialize_row({"created_at": row["created_at"]})["created_at"],
            }
            for row in rows
        ]

    def create_alert_subscription(
        self,
        chat_id: str,
        city: str | None,
        neighborhood: str | None,
        max_price: int | None,
        min_rooms: float | None,
        label: str,
        notify_new: bool,
        notify_price_drop: bool,
    ) -> dict[str, Any]:
        with self._db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO alert_subscriptions (
                    chat_id, city, neighborhood, max_price, min_rooms,
                    label, notify_new, notify_price_drop
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, created_at
                """,
                (
                    chat_id,
                    city,
                    neighborhood,
                    max_price,
                    min_rooms,
                    label,
                    notify_new,
                    notify_price_drop,
                ),
            )
            row = dict(cur.fetchone())

        created_at = serialize_row({"created_at": row["created_at"]})["created_at"]
        return {
            "id": row["id"],
            "created_at": created_at,
            "message": "Subscribed",
        }

    def delete_alert_subscription(self, sub_id: int) -> bool:
        with self._db.cursor() as cur:
            cur.execute(
                "DELETE FROM alert_subscriptions WHERE id = %s RETURNING id",
                (sub_id,),
            )
            return cur.fetchone() is not None

    def list_city_subscriptions(self) -> list[dict[str, Any]]:
        with self._db.cursor() as cur:
            cur.execute(
                """
                SELECT id, city_name, city_code, min_rooms, active, added_at
                FROM city_subscriptions
                ORDER BY city_name
                """
            )
            return serialize_rows([dict(r) for r in cur.fetchall()])

    def add_city_subscription(
        self,
        city_name: str,
        city_code: str,
        min_rooms: float | None,
    ) -> dict[str, Any]:
        with self._db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO city_subscriptions (city_name, city_code, min_rooms, active)
                VALUES (%s, %s, %s, TRUE)
                ON CONFLICT (city_name) DO UPDATE SET
                    city_code = EXCLUDED.city_code,
                    min_rooms = EXCLUDED.min_rooms,
                    active = TRUE
                RETURNING id, city_name, city_code, min_rooms, active, added_at
                """,
                (city_name, city_code, min_rooms),
            )
            return serialize_row(dict(cur.fetchone()))

    def remove_city_subscription(self, city_name: str) -> bool:
        with self._db.cursor() as cur:
            cur.execute(
                "UPDATE city_subscriptions SET active = FALSE WHERE city_name = %s RETURNING id",
                (city_name,),
            )
            return cur.fetchone() is not None

    def list_active_cities(self) -> list[dict[str, Any]]:
        with self._db.cursor() as cur:
            cur.execute(
                """
                SELECT city_name, city_code, min_rooms
                FROM city_subscriptions
                WHERE active = TRUE
                ORDER BY city_name
                """
            )
            rows = [dict(r) for r in cur.fetchall()]

        return [
            {
                "city_name": row["city_name"],
                "city_code": row["city_code"],
                "min_rooms": float(row["min_rooms"]) if row["min_rooms"] is not None else None,
            }
            for row in rows
        ]

    def get_active_city(self, city_name: str) -> dict[str, Any] | None:
        with self._db.cursor() as cur:
            cur.execute(
                """
                SELECT city_name, city_code, min_rooms
                FROM city_subscriptions
                WHERE active = TRUE AND city_name = %s
                """,
                (city_name,),
            )
            row = cur.fetchone()

        if not row:
            return None

        row = dict(row)
        return {
            "city_name": row["city_name"],
            "city_code": row["city_code"],
            "min_rooms": float(row["min_rooms"]) if row["min_rooms"] is not None else None,
        }

    def ensure_default_cities(self) -> None:
        with self._db.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS count FROM city_subscriptions WHERE active = TRUE")
            count = int(cur.fetchone()["count"])

        if count > 0:
            return

        self.add_city_subscription("רחובות", "8400", None)
        self.add_city_subscription("חיפה", "4000", None)
