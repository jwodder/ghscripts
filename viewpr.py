#!/usr/bin/env -S pipx run
# /// script
# requires-python = ">=3.8"
# dependencies = ["ghrepo ~= 0.5", "ghreq ~= 0.1", "ghtoken ~= 0.1"]
# ///

"""
Determines the GitHub pull request created from the current branch in the local
repository and opens it in a web browser
"""

from __future__ import annotations
import sys
import webbrowser
import ghrepo
from ghreq import Client
from ghtoken import get_ghtoken


def main() -> None:
    local = ghrepo.get_local_repo()
    branch = ghrepo.get_current_branch()
    with Client(token=get_ghtoken()) as client:
        head = client.get(local.api_url)
        if head["fork"]:
            base = head["parent"]
        else:
            base = head
        pulls = client.paginate(
            f"{base['url']}/pulls",
            params={
                "state": "all",
                "head": f"{local.owner}:{branch}",
                "sort": "created",
                "direction": "desc",
            },
        )
        if (pr := next(pulls, None)) is not None:
            webbrowser.open(pr["html_url"])
        else:
            sys.exit(
                f"No pull request found for {branch!r} in {base['full_name']}"
                f" from {local}"
            )


if __name__ == "__main__":
    main()
