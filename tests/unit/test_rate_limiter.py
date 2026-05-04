"""Unit test for rate limiter creation."""


def test_rate_limiter_instantiated():
    from app.core.rate_limit import limiter

    assert limiter is not None
