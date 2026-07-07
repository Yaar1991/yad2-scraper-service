"""full schema tables

Revision ID: 20260528_000002
Revises: 20260528_000001
Create Date: 2026-05-28 16:00:00
"""

from alembic import op

revision = "20260528_000002"
down_revision = "20260528_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS listings (
            id VARCHAR(50) PRIMARY KEY,
            ad_number VARCHAR(50),
            link_token VARCHAR(50),
            street VARCHAR(255),
            property_type VARCHAR(100),
            description_line TEXT,
            city VARCHAR(100),
            neighborhood VARCHAR(100),
            price VARCHAR(50),
            price_numeric INTEGER,
            currency VARCHAR(10),
            rooms VARCHAR(20),
            floor VARCHAR(20),
            size_sqm VARCHAR(50),
            date_added TIMESTAMP,
            updated_at VARCHAR(100),
            contact_name VARCHAR(255),
            is_merchant BOOLEAN DEFAULT FALSE,
            merchant_name VARCHAR(255),
            latitude DECIMAL(10, 8),
            longitude DECIMAL(11, 8),
            image_url TEXT,
            images_count INTEGER DEFAULT 0,
            amenities JSONB,
            raw_data JSONB,
            first_seen_at TIMESTAMP DEFAULT NOW(),
            last_seen_at TIMESTAMP DEFAULT NOW(),
            is_active BOOLEAN DEFAULT TRUE
        );

        CREATE INDEX IF NOT EXISTS idx_listings_city ON listings(city);
        CREATE INDEX IF NOT EXISTS idx_listings_neighborhood ON listings(neighborhood);
        CREATE INDEX IF NOT EXISTS idx_listings_price ON listings(price_numeric);
        CREATE INDEX IF NOT EXISTS idx_listings_rooms ON listings(rooms);
        CREATE INDEX IF NOT EXISTS idx_listings_last_seen ON listings(last_seen_at);
        CREATE INDEX IF NOT EXISTS idx_listings_is_active ON listings(is_active);

        CREATE TABLE IF NOT EXISTS price_history (
            id SERIAL PRIMARY KEY,
            listing_id VARCHAR(50) NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
            price VARCHAR(50),
            price_numeric INTEGER,
            recorded_at TIMESTAMP DEFAULT NOW(),
            scrape_run_id INTEGER
        );

        CREATE INDEX IF NOT EXISTS idx_price_history_listing ON price_history(listing_id);
        CREATE INDEX IF NOT EXISTS idx_price_history_recorded ON price_history(recorded_at);
        CREATE INDEX IF NOT EXISTS idx_price_history_listing_recorded
            ON price_history(listing_id, recorded_at DESC);

        CREATE TABLE IF NOT EXISTS scraper_state (
            key VARCHAR(50) PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS alert_subscriptions (
            id SERIAL PRIMARY KEY,
            chat_id VARCHAR(50) NOT NULL,
            city VARCHAR(100),
            neighborhood VARCHAR(100),
            max_price INTEGER,
            min_rooms REAL,
            label VARCHAR(255),
            notify_new BOOLEAN DEFAULT TRUE,
            notify_price_drop BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS city_subscriptions (
            id SERIAL PRIMARY KEY,
            city_name VARCHAR(100) NOT NULL UNIQUE,
            city_code VARCHAR(20) NOT NULL,
            active BOOLEAN DEFAULT TRUE,
            added_at TIMESTAMP DEFAULT NOW(),
            min_rooms REAL
        );
        """
    )

    for col, coltype, default in [
        ("total_pages", "INTEGER", "NULL"),
        ("pages_scraped", "INTEGER", "0"),
        ("pages_failed", "INTEGER", "0"),
        ("listings_updated", "INTEGER", "0"),
        ("price_changes", "INTEGER", "0"),
        ("error_message", "TEXT", "NULL"),
        ("run_type", "VARCHAR(100)", "'full'"),
        ("last_page_scraped", "INTEGER", "0"),
        ("scraped_pages", "JSONB", "'[]'"),
    ]:
        op.execute(
            f"ALTER TABLE scrape_runs ADD COLUMN IF NOT EXISTS {col} {coltype} DEFAULT {default};"
        )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS city_subscriptions;
        DROP TABLE IF EXISTS alert_subscriptions;
        DROP TABLE IF EXISTS scraper_state;
        DROP TABLE IF EXISTS price_history;
        DROP TABLE IF EXISTS listings;
        """
    )
