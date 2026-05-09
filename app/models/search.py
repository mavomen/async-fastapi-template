"""Full-text search mixin for PostgreSQL tsvector."""

from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column


class SearchMixin:
    """Mixin that adds a tsvector column and a search_query classmethod."""

    search_vector: Mapped[str] = mapped_column(TSVECTOR, nullable=True)

    @classmethod
    def search_query(cls, search_term: str):
        """Return a SQLAlchemy expression using websearch_to_tsquery."""
        expr = func.websearch_to_tsquery("english", search_term)
        return cls.search_vector.op("@@")(expr)
