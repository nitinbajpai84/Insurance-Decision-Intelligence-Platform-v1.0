from __future__ import annotations

import argparse
from urllib.parse import quote


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="URL-encode a Supabase database password for a Postgres connection string.")
    parser.add_argument("password", help="Raw database password from Supabase")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    encoded = quote(args.password, safe="")
    print(encoded)
    print()
    print("Use it like this:")
    print(f"SUPABASE_DB_URL=postgresql://postgres:{encoded}@db.utwsmuzwubykpzdcizac.supabase.co:5432/postgres")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
