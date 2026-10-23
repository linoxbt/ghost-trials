"""Operator CLI for workspace review budgets, for deployments without an operator token.

Run it where the API's database lives (inside the container on the VPS):
    python -m ghost_trials.budget list
    python -m ghost_trials.budget set <organization_id> <cents>
"""
import argparse

from .accounts import Accounts
from .config import get_settings
from .durable import DurableStore


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="python -m ghost_trials.budget", description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="show every workspace with its budget limit and reserved cents")
    allocate = commands.add_parser("set", help="set one workspace's review budget limit (never below what is reserved)")
    allocate.add_argument("organization_id")
    allocate.add_argument("cents", type=int)
    args = parser.parse_args(argv)
    settings = get_settings()
    accounts = Accounts(DurableStore(settings.ghost_data_path), settings)
    if args.command == "set":
        if args.cents < 0:
            parser.error("cents must be zero or more")
        accounts.allocate_budget(args.organization_id, args.cents)
    with accounts.store.connect() as db:
        accounts.schema(db)
        rows = db.execute("SELECT o.id, o.name, COALESCE(b.limit_cents,0), COALESCE(b.used_cents,0) FROM organizations o "
                          "LEFT JOIN budgets b ON b.id=o.id ORDER BY o.created").fetchall()
    for organization_id, name, limit, used in rows:
        if args.command == "list" or organization_id == args.organization_id:
            print(f"{organization_id}\t{name}\tlimit={limit}¢\treserved={used}¢")


if __name__ == "__main__":
    main()
