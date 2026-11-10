"""Fill a demo account with ~3 months of realistic data.

    1. Sign up in the app with the demo email (e.g. demo@hisabify.app).
    2. cd backend && python -m scripts.seed_demo demo@hisabify.app [--reset]

Uses DATABASE_URL from .env. Looks the user up by email in Supabase's auth.users table.
--reset wipes that account's existing data first (asks for confirmation).
"""

import argparse
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.services.account import wipe_user_data
from app.services.demo_seed import DemoSeedError, seed_demo


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("email")
    parser.add_argument("--reset", action="store_true", help="wipe this account's data first")
    args = parser.parse_args()

    settings = Settings()
    if not settings.database_url:
        print("DATABASE_URL is not set.")
        return 2
    engine = create_engine(settings.database_url, connect_args={"prepare_threshold": None})
    with Session(engine) as db:
        user_id = db.scalar(
            text("SELECT id FROM auth.users WHERE lower(email) = lower(:e)"), {"e": args.email}
        )
        if user_id is None:
            print(f"No user with email {args.email}. Sign up in the app first.")
            return 1
        if args.reset:
            answer = input(f"Wipe ALL data for {args.email}? Type DELETE to confirm: ")
            if answer != "DELETE":
                print("Cancelled.")
                return 1
            wipe_user_data(db, user_id)
        try:
            result = seed_demo(db, user_id)
        except DemoSeedError as exc:
            print(exc)
            return 1
    print(f"Seeded {result['transactions']} transactions ({result['from']} → {result['to']}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
