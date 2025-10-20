#!/usr/bin/env -S pipx run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#    "click ~= 8.0",
#    "ghtoken ~= 0.1",
#    "python-dateutil ~= 2.9",
#    "requests ~= 2.20",
#    "txtble ~= 0.12",
# ]
# ///

from __future__ import annotations
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, tzinfo
import json
import logging
from time import sleep
from types import TracebackType
from typing import Any
import click
from dateutil.tz import gettz
from ghtoken import get_ghtoken
import requests
from txtble import Txtble

log = logging.getLogger()

GRAPHQL_API_URL = "https://api.github.com/graphql"

MAX_RETRIES = 5
RETRY_STATUSES = (500, 502, 503, 504)
BACKOFF_FACTOR = 1.25
MAX_BACKOFF = 120

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


class Client:
    def __init__(self, token: str) -> None:
        self.s = requests.Session()
        self.s.headers["Authorization"] = f"bearer {token}"

    def __enter__(self) -> Client:
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_val: BaseException | None,
        _exc_tb: TracebackType | None,
    ) -> None:
        self.s.close()

    def query(self, query: str, variables: dict[str, Any]) -> dict:
        i = 0
        while True:
            r = self.s.post(
                GRAPHQL_API_URL,
                json={"query": query, "variables": variables},
            )
            if r.status_code in RETRY_STATUSES:
                if i + 1 < MAX_RETRIES:
                    delay = min(BACKOFF_FACTOR * 2**i, MAX_BACKOFF)
                    log.warning(
                        "GraphQL request returned %d; waiting %f seconds and retrying",
                        r.status_code,
                        delay,
                    )
                    sleep(delay)
                    i += 1
                    continue
                else:
                    log.error(
                        "GraphQL request returned %d; out of retries", r.status_code
                    )
                    raise APIException(r)
            elif not r.ok:
                raise APIException(r)
            else:
                break
        data = r.json()
        if data.get("errors"):
            raise APIException(r)
        return r.json()["data"]  # type: ignore[no-any-return]

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


class APIException(Exception):
    def __init__(self, response: requests.Response) -> None:
        self.response = response

    def __str__(self) -> str:
        if self.response.ok:
            msg = "GraphQL API error for URL: {0.url}\n"
        elif 400 <= self.response.status_code < 500:
            msg = "{0.status_code} Client Error: {0.reason} for URL: {0.url}\n"
        elif 500 <= self.response.status_code < 600:
            msg = "{0.status_code} Server Error: {0.reason} for URL: {0.url}\n"
        else:
            msg = "{0.status_code} Unknown Error: {0.reason} for URL: {0.url}\n"
        msg = msg.format(self.response)
        try:
            resp = self.response.json()
        except ValueError:
            msg += self.response.text
        else:
            msg += json.dumps(resp, sort_keys=True, indent=4)
        return msg


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
    Show a table of the number of commits made to GitHub repositories over the
    past several days
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
