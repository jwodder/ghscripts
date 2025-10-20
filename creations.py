#!/usr/bin/env -S pipx run
# /// script
# requires-python = ">=3.11"
# dependencies = ["click ~= 8.2", "ghreq ~= 0.1", "ghtoken ~= 0.1"]
# ///

from __future__ import annotations
from datetime import date, datetime, time, timedelta, timezone
import click
from ghreq import Client
from ghtoken import get_ghtoken

__author__ = "John Thorvald Wodder II"
__author_email__ = "ghscripts@varonathe.org"
__license__ = "MIT"
__url__ = "https://github.com/jwodder/ghscripts"


class DateArg(click.ParamType):
    name = "date"

    def convert(
        self,
        value: str | date,
        param: click.Parameter | None,
        ctx: click.Context | None,
    ) -> date:
        if isinstance(value, str):
            try:
                return date.fromisoformat(value)
            except ValueError as e:
                self.fail(str(e), param, ctx)
        else:
            return value

    def get_metavar(self, param: click.Parameter, ctx: click.Context) -> str:
        return "YYYY-MM-DD"


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--since",
    type=DateArg(),
    help="The earliest date for which to show events [default: yesterday]",
)
def main(since: date | None) -> None:
    """
    List various actions performed on GitHub since a given date

    This script requires a GitHub access token with appropriate permissions in
    order to run.  Specify the token via the `GH_TOKEN` or `GITHUB_TOKEN`
    environment variable (possibly in an `.env` file), by storing a token with
    the `gh` or `hub` command, or by setting the `hub.oauthtoken` Git config
    option in your `~/.gitconfig` file.
    """
    if since is None:
        since_dt = datetime.now(timezone.utc) - timedelta(days=1)
    else:
        since_dt = datetime.combine(since, time.min).astimezone()
    with Client(token=get_ghtoken()) as client:
        whoami = client.get("/user")["login"]
        for ev in client.paginate(f"/users/{whoami}/events"):
            created = datetime.fromisoformat(ev["created_at"])
            if created < since_dt:
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
                    if action == "closed" and prdata["merged"]:
                        action = "merged"
                    number = prdata["number"]
                    # Removed from payload as part of
                    # <https://github.blog/changelog/2025-08-08-upcoming-changes-to-github-events-api-payloads/>
                    # title = prdata["title"]
                    title = client.get(prdata["url"])["title"]
                    print(f"[{ts}] {action.title()} PR {repo}#{number}: {title}")
                case ("ReleaseEvent", "published"):
                    tag = ev["payload"]["release"]["tag_name"]
                    name = ev["payload"]["release"]["name"]
                    print(f"[{ts}] {action.title()} release for {repo}@{tag}: {name}")
                case _:
                    pass


if __name__ == "__main__":
    main()
