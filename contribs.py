#!/usr/bin/env -S pipx run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#    "click ~= 8.0",
#    "ghtoken ~= 0.1",
#    "ghreq ~= 0.6",
#    "python-dateutil ~= 2.9",
#    "txtble ~= 0.12",
# ]
# ///

from __future__ import annotations
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, tzinfo
import json
from typing import Any
import click
from dateutil.tz import gettz
import ghreq
from ghtoken import get_ghtoken
from txtble import Txtble

__author__ = "John Thorvald Wodder II"
__author_email__ = "ghscripts@varonathe.org"
__license__ = "MIT"
__url__ = "https://github.com/jwodder/ghscripts"

REPO_QTY_GUESS = 10

QUERY = """
query ($from: DateTime!, $to: DateTime!, $maxRepositories: Int!) {
    viewer {
        contributionsCollection (from: $from, to: $to) {
            totalRepositoriesWithContributedCommits
            commitContributionsByRepository (maxRepositories: $maxRepositories) {
                repository {
                    nameWithOwner
                }
                contributions {
                    totalCount
                }
            }
        }
    }
}
"""


class Client(ghreq.Client):
    def query(self, query: str, variables: dict[str, Any]) -> dict:
        data = self.graphql(query, variables)
        if err := data.get("errors"):
            raise GraphQLException(err)
        return data["data"]  # type: ignore[no-any-return]

    def get_contributions(self, from_dt: datetime, to_dt: datetime) -> dict[str, int]:
        # Note: Batching the requests doesn't speed things up.  I tried.
        data = self.query(
            QUERY,
            {
                "from": from_dt.isoformat(),
                "to": to_dt.isoformat(),
                "maxRepositories": REPO_QTY_GUESS,
            },
        )
        real_qty = data["viewer"]["contributionsCollection"][
            "totalRepositoriesWithContributedCommits"
        ]
        assert isinstance(real_qty, int)
        if real_qty > REPO_QTY_GUESS:
            data = self.query(
                QUERY,
                {
                    "from": from_dt.isoformat(),
                    "to": to_dt.isoformat(),
                    "maxRepositories": real_qty,
                },
            )
        return {
            ccbr["repository"]["nameWithOwner"]: ccbr["contributions"]["totalCount"]
            for ccbr in data["viewer"]["contributionsCollection"][
                "commitContributionsByRepository"
            ]
        }


class GraphQLException(Exception):
    def __init__(self, errors: list[dict[str, Any]]) -> None:
        self.errors = errors
        super().__init__(errors)

    def __str__(self) -> str:
        try:
            lines = []
            if len(self.errors) == 1:
                lines.append("GraphQL API error:")
            else:
                lines.append("GraphQL API errors:")
            first = True
            for e in self.errors:
                if first:
                    first = False
                else:
                    lines.append("---")
                for k, v in e.items():
                    k = k.title()
                    if isinstance(v, str | int | bool):
                        lines.append(f"{k}: {v}")
                    else:
                        lines.append(k + ": " + json.dumps(v, sort_keys=True))
            return "\n".join(lines)
        except Exception:
            return "MALFORMED GRAPHQL ERROR:\n" + json.dumps(
                self.errors, sort_keys=True, indent=True
            )


@dataclass
class ContribTabulator:
    contribs: dict[str, dict[date, int]] = field(init=False, default_factory=dict)
    dates: set[date] = field(init=False, default_factory=set)
    totals: dict[date, int] = field(init=False, default_factory=dict)

    def add(self, d: date, contribs: dict[str, int]) -> None:
        self.totals[d] = sum(contribs.values())
        for repo, date2contribs in self.contribs.items():
            date2contribs[d] = contribs.pop(repo, 0)
        for new_repo, count in contribs.items():
            self.contribs[new_repo] = {d: count}
            for old_date in self.dates:
                self.contribs[new_repo][old_date] = 0
        self.dates.add(d)

    def to_table(self) -> str:
        dates = sorted(self.dates)
        tbl = Txtble(
            headers=["Repository", *dates, "Total"],
            align=["l"],
            align_fill="r",
            padding=1,
        )
        for repo, contribs in sorted(self.contribs.items()):
            tbl.append(
                [repo, *(contribs[d] or None for d in dates), sum(contribs.values())]
            )
        tbl.append(
            [
                "TOTAL",
                *(self.totals[d] or None for d in dates),
                sum(self.totals.values()),
            ]
        )
        return tbl.show()


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "-d",
    "--days",
    type=int,
    default=7,
    show_default=True,
    help="How many days back to show",
)
@click.option(
    "-H", "--highlight", is_flag=True, help="Color alternating rows of the table"
)
def main(days: int, highlight: bool) -> None:
    """
    Show a table of the number of commits per repository per day made to GitHub
    repositories over the past several days

    This script requires a GitHub access token with appropriate permissions in
    order to run.  Specify the token via the `GH_TOKEN` or `GITHUB_TOKEN`
    environment variable (possibly in an `.env` file), by storing a token with
    the `gh` or `hub` command, or by setting the `hub.oauthtoken` Git config
    option in your `~/.gitconfig` file.
    """
    tz = gettz()
    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)
    tbl = ContribTabulator()
    with Client(token=get_ghtoken()) as client:
        for d, from_dt, to_dt in iterdates(start_date, end_date, tz):
            contribs = client.get_contributions(from_dt, to_dt)
            tbl.add(d, contribs)
    s = tbl.to_table()
    if highlight:
        lines = s.splitlines()
        for i in range(4, len(lines) - 1, 2):
            lines[i] = f"|\x1b[30;48;5;227m{lines[i][1:-1]}\x1b[m|"
        s = "\n".join(lines)
    print(s)


def iterdates(
    start: date, end: date, tz: tzinfo
) -> Iterator[tuple[date, datetime, datetime]]:
    d = start
    while d <= end:
        start_dt = datetime.combine(d, time(0, 0, 0), tz)
        end_dt = datetime.combine(d, time(23, 59, 59), tz)
        yield (d, start_dt, end_dt)
        d += timedelta(days=1)


if __name__ == "__main__":
    main()
