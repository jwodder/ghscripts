#!/usr/bin/env -S pipx run
# /// script
# requires-python = ">=3.11"
# dependencies = ["click >= 7.0", "ghreq ~= 0.1", "ghtoken ~= 0.1"]
# ///

from __future__ import annotations
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
import click
import ghreq
from ghtoken import GHTokenNotFound, get_ghtoken

WINDOW = timedelta(days=3)


class Client(ghreq.Client):
    def get_repos(self, owner: str | None) -> Iterator[dict]:
        if owner is None:
            return self.paginate("/user/repos", params={"affiliation": "owner"})
        else:
            return self.paginate(f"/users/{owner}/repos")

    def get_runs(self, repo: str, created_after: datetime) -> Iterator[dict]:
        # This omits queued runs:
        # return self.paginate(
        #     f"/repos/{repo}/actions/runs",
        #     params={"created": ">" + created_after.isoformat(timespec="seconds")},
        # )
        for run in self.paginate(f"/repos/{repo}/actions/runs"):
            if datetime.fromisoformat(run["created_at"]) <= created_after:
                break
            yield run


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("-F", "--include-forks", is_flag=True, help="Include runs in forks")
@click.option(
    "-P",
    "--include-private",
    is_flag=True,
    help="Include runs in private repositories",
)
@click.argument("owner", required=False)
def main(owner: str | None, include_forks: bool, include_private: bool) -> None:
    """
    List all active GitHub Actions workflow runs in repositories owned by a
    given user
    """
    try:
        token = get_ghtoken()
    except GHTokenNotFound:
        raise click.UsageError(
            "GitHub token not found.  Set via GH_TOKEN, GITHUB_TOKEN, gh, hub,"
            " or hub.oauthtoken."
        )
    created_after = datetime.now(timezone.utc) - WINDOW
    with Client(token=token) as client:
        first = True
        for repo in client.get_repos(owner):
            if repo["archived"]:
                continue
            if repo["fork"] and not include_forks:
                continue
            if repo["private"] and not include_private:
                continue
            running = [
                run
                for run in client.get_runs(repo["full_name"], created_after)
                if run["status"] != "completed"
            ]
            if running:
                if first:
                    first = False
                else:
                    print()
                header = repo["full_name"]
                print(header)
                print("-" * len(header))
                for run in running:
                    s = "{name} #{run_number}".format_map(run)
                    if (attempt := run["run_attempt"]) is not None and attempt > 1:
                        s += f"(attempt {attempt})"
                    if run["display_title"] != run["name"]:
                        s += f" - {run['display_title']}"
                    event = run["event"]
                    if event == "pull_request":
                        event = "PR"
                    s += f" - {event}"
                    if run["pull_requests"]:
                        s += " " + ", ".join(
                            "#{number}".format_map(pr) for pr in run["pull_requests"]
                        )
                    if branch := run["head_branch"]:
                        s += f" - {branch}"
                    created_at = datetime.fromisoformat(run["created_at"]).astimezone()
                    s += f" - {run['status']} - {created_at}"
                    print(s)


if __name__ == "__main__":
    main()
