def extract_listings(data: dict) -> list[dict]:
    """Extract normalized listing dicts from a Yad2 feed API response."""
    listings = []
    for item in data.get("feed", {}).get("feed_items", []):
        if not isinstance(item, dict) or item.get("type") != "ad":
            continue

        images = item.get("images_urls", []) or []
        row4 = {}
        for e in (item.get("row_4") or []):
            if isinstance(e, dict):
                row4[e.get("key", "")] = e.get("value", "")

        listing = {
            "id": item.get("id", item.get("link_token", "")),
            "ad_number": item.get("ad_number", ""),
            "link_token": item.get("link_token", ""),
            "street": item.get("title_1", item.get("street", "")),
            "property_type": item.get("title_2", item.get("HomeTypeID_text", "")),
            "description_line": item.get("row_2", ""),
            "city": item.get("city", ""),
            "neighborhood": item.get("neighborhood", ""),
            "price": item.get("price", ""),
            "currency": item.get("currency", ""),
            "rooms": item.get("Rooms_text", str(row4.get("rooms", ""))),
            "floor": str(row4.get("floor", item.get("line_2", ""))),
            "size_sqm": item.get("square_meters", str(row4.get("SquareMeter", ""))),
            "date_added": item.get("date_added", ""),
            "updated_at": item.get("updated_at", ""),
            "contact_name": item.get("contact_name", ""),
            "is_merchant": item.get("merchant", False),
            "merchant_name": item.get("merchant_name", ""),
            "coordinates": item.get("coordinates", {}),
            "image_url": images[0] if images else "",
            "images_urls": images[:5],
            "images_count": len(images),
            "amenities": {
                "parking": item.get("Parking_text", ""),
                "elevator": item.get("Elevator_text", ""),
                "ac": item.get("AirConditioner_text", ""),
                "mamad": item.get("mamad_text", ""),
                "storage": item.get("storeroom_text", ""),
            },
        }
        if listing["id"]:
            listings.append(listing)

    return listings
