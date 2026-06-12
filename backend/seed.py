"""Convenience wrapper so ``python seed.py`` works from the backend root.

Creates the app context (which builds the schema) and loads demo data.
"""
from app import create_app
from app.seed import seed

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        seed()
