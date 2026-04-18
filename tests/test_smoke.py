"""Smoke tests: no network, no secrets."""

from agnes.config.settings import Settings


def test_settings_instantiates() -> None:
    s = Settings()
    assert s.db_path.name == "db.sqlite"
    assert s.gemini_model


def test_imports() -> None:
    from agnes.data import db_loader  # noqa: F401
    from agnes.graph import cognee_cloud_client  # noqa: F401
    from agnes.retrieval import google_cloud_client  # noqa: F401
    from agnes.utils import logging as agnes_logging  # noqa: F401

    assert agnes_logging.configure_logging is not None
