from sqlalchemy.engine import make_url

from app.core.config import Settings


def test_database_url_uses_safe_url_construction_for_special_password_chars():
    settings = Settings(
        database_url_value=None,
        postgres_host="127.0.0.1",
        postgres_port=5432,
        postgres_user="cad_user",
        postgres_password="pa@ss/w:rd?",
        postgres_db="cad_db",
    )

    url = settings.database_url
    parsed = make_url(url)

    assert parsed.drivername == "postgresql+asyncpg"
    assert parsed.username == "cad_user"
    assert parsed.password == "pa@ss/w:rd?"
    assert parsed.host == "127.0.0.1"
    assert parsed.port == 5432
    assert parsed.database == "cad_db"
    assert "pa@ss/w:rd?" not in url


def test_explicit_database_url_takes_precedence():
    settings = Settings(
        database_url="postgresql+asyncpg://explicit:secret@db.example/cad",
        postgres_host="127.0.0.1",
        postgres_user="ignored",
        postgres_password="ignored",
        postgres_db="ignored",
    )

    assert settings.database_url == "postgresql+asyncpg://explicit:secret@db.example/cad"


def test_explicit_postgresql_url_is_normalized_for_asyncpg():
    settings = Settings(database_url="postgresql://rag:secret@127.0.0.1:5432/raganything")

    assert settings.database_url.startswith("postgresql+asyncpg://")
