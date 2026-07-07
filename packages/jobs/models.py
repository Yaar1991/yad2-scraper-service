from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ScrapeCityJob:
    city_name: str
    city_code: str
    min_rooms: float | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "city_name": self.city_name,
            "city_code": self.city_code,
            "min_rooms": self.min_rooms,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ScrapeCityJob":
        min_rooms = payload.get("min_rooms")
        return cls(
            city_name=payload["city_name"],
            city_code=payload["city_code"],
            min_rooms=float(min_rooms) if min_rooms is not None else None,
        )


@dataclass(frozen=True)
class NotifyScrapeCompleteJob:
    run_id: int
    run_type: str
    pages_scraped: int
    total_pages: int
    listings_new: int
    listings_updated: int
    price_changes: int
    duration_min: int

    def to_payload(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "run_type": self.run_type,
            "pages_scraped": self.pages_scraped,
            "total_pages": self.total_pages,
            "listings_new": self.listings_new,
            "listings_updated": self.listings_updated,
            "price_changes": self.price_changes,
            "duration_min": self.duration_min,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "NotifyScrapeCompleteJob":
        return cls(
            run_id=int(payload["run_id"]),
            run_type=str(payload["run_type"]),
            pages_scraped=int(payload["pages_scraped"]),
            total_pages=int(payload["total_pages"]),
            listings_new=int(payload["listings_new"]),
            listings_updated=int(payload["listings_updated"]),
            price_changes=int(payload["price_changes"]),
            duration_min=int(payload["duration_min"]),
        )
