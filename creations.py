#!/usr/bin/env -S pipx run
# /// script
# requires-python = ">=3.11"
# dependencies = ["ghreq ~= 0.1", "ghtoken ~= 0.1"]
# ///

from __future__ import annotations
import argparse
from collections.abc import Sequence
from datetime import date, datetime, time, timedelta, timezone
import textwrap
from typing import Any
from ghreq import Client
from ghtoken import get_ghtoken

__author__ = "John Thorvald Wodder II"
__author_email__ = "ghscripts@varonathe.org"
__license__ = "MIT"
__url__ = "https://github.com/jwodder/ghscripts"


class DaysAgo(argparse.Action):
    def __call__(
        self,
        _parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        value: str | Sequence[Any] | None,
        _option_string: str | None = None,
    ) -> None:
        if not isinstance(value, str):
            raise TypeError(value)  # pragma: no cover
        days = int(value)
        if days < 1:
            raise ValueError("--days argument must be positive")
        namespace.since = days_ago(days)


def days_ago(days: int) -> date:
    return datetime.now(timezone.utc) - timedelta(days=days)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=textwrap.dedent(
            """
            List various actions performed on GitHub since a given date

            This script requires a GitHub access token with appropriate permissions in
            order to run.  Specify the token via the `GH_TOKEN` or `GITHUB_TOKEN`
            environment variable (possibly in an `.env` file), by storing a token with
            the `gh` or `hub` command, or by setting the `hub.oauthtoken` Git config
            option in your `~/.gitconfig` file.
            """
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--since",
        type=lambda s: datetime.combine(date.fromisoformat(s), time.min).astimezone(),
        metavar="YYYY-MM-DD",
        help="The earliest date for which to show events [default: yesterday]",
        default=days_ago(1),
    )
    parser.add_argument(
        "-d",
        "--days",
        action=DaysAgo,
        help="How many days back to show events; overrides --since",
    )
    args = parser.parse_args()
    with Client(token=get_ghtoken()) as client:
        whoami = client.get("/user")["login"]
        for ev in client.paginate(f"/users/{whoami}/events"):
            created = datetime.fromisoformat(ev["created_at"])
            if created < args.since:
                break
            ts = created.astimezone().strftime("%Y-%m-%d %H:%M")
            repo = ev["repo"]["name"]
            action = ev["payload"].get("action")
            match (ev["type"], action):
                case ("CreateEvent", _) if ev["payload"]["ref_type"] == "repository":
                    print(f"[{ts}] Created repository {repo}")
                case ("ForkEvent", _):
                    forkee = ev["payload"]["forkee"]["full_name"]
                    print(f"[{ts}] Forked repository {forkee}")
                case ("IssuesEvent", "opened" | "closed" | "reopened"):
                    number = ev["payload"]["issue"]["number"]
                    title = ev["payload"]["issue"]["title"]
                    print(f"[{ts}] {action.title()} issue {repo}#{number}: {title}")
                case ("PullRequestEvent", "opened" | "closed" | "reopened"):
                    prdata = ev["payload"]["pull_request"]
                    fullpr = client.get(prdata["url"])
                    if action == "closed" and fullpr["merged"]:
                        action = "merged"
                    number = prdata["number"]
                    title = fullpr["title"]
                    print(f"[{ts}] {action.title()} PR {repo}#{number}: {title}")
                case ("ReleaseEvent", "published"):
                    tag = ev["payload"]["release"]["tag_name"]
                    name = ev["payload"]["release"]["name"]
                    print(f"[{ts}] {action.title()} release for {repo}@{tag}: {name}")
                case _:
                    pass


if __name__ == "__main__":
    main()
