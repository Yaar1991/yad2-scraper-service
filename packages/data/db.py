from contextlib import contextmanager

from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool


class Database:
    def __init__(self, database_url: str, minconn: int = 1, maxconn: int = 10):
        self._pool = ThreadedConnectionPool(
            minconn,
            maxconn,
            database_url,
            cursor_factory=RealDictCursor,
        )

    @contextmanager
    def connection(self):
        conn = self._pool.getconn()
        try:
            yield conn
        finally:
            try:
                conn.rollback()
            except Exception:
                pass
            self._pool.putconn(conn)

    @contextmanager
    def cursor(self):
        with self.connection() as conn:
            cur = conn.cursor()
            try:
                yield cur
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                cur.close()

    def ping(self) -> None:
        with self.cursor() as cur:
            cur.execute("SELECT 1")

    def close(self) -> None:
        self._pool.closeall()
