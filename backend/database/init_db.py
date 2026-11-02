from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.session import create_database_engine


def main():
    settings = Settings.from_environment()
    engine = create_database_engine(settings)
    try:
        initialize_database(engine)
        print(f"SQLite initialized without resetting data: {settings.database_path}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
