#!/usr/bin/env -S pipx run
# /// script
# requires-python = ">=3.9"
# dependencies = ["ghreq ~= 0.1", "ghtoken ~= 0.1"]
# ///

from __future__ import annotations
import argparse
from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum
import ghreq
from ghtoken import get_ghtoken

__author__ = "John Thorvald Wodder II"
__author_email__ = "ghscripts@varonathe.org"
__license__ = "MIT"
__url__ = "https://github.com/jwodder/ghscripts"


class Reaction(Enum):
    THUMBS_DOWN = ("👎", "-1")
    THUMBS_UP = ("👍", "+1")
    LAUGH = ("😄", "laugh")
    HOORAY = ("🎉", "hooray")
    CONFUSED = ("😕", "confused")
    HEART = ("❤️", "heart")
    ROCKET = ("🚀", "rocket")
    EYES = ("👀", "eyes")

    def __new__(cls, value, shortcut):
        obj = object.__new__(cls)
        obj._value_ = value
        obj.shortcut = shortcut
        return obj

    @classmethod
    def from_shortcut(cls, shortcut: str) -> Reaction:
        for r in Reaction:
            if r.shortcut == shortcut:
                return r
        raise ValueError(shortcut)


class Client(ghreq.Client):
    def get_repositories(self) -> Iterator[str]:
        for repo in self.paginate("/user/repos", params={"affiliation": "owner"}):
            if not repo["archived"] and not repo["fork"]:
                yield repo["full_name"]

    def get_issue_reactions(self, repo: str) -> Iterator[Issue]:
        for issue in self.paginate(f"/repos/{repo}/issues"):
            yield Issue(
                title=issue["title"],
                url=issue["html_url"],
                is_pr=issue.get("pull_request") is not None,
                reactions={
                    Reaction.from_shortcut(k): v
                    for k, v in issue["reactions"].items()
                    if k not in ("url", "total_count")
                },
            )


@dataclass
class Issue:
    title: str
    url: str
    is_pr: bool
    reactions: dict[Reaction, int]

    def has_reactions(self) -> bool:
        return any(qty > 0 for qty in self.reactions.values())

    def reaction_str(self) -> str:
        strs = []
        for r in Reaction:
            if (qty := self.reactions.get(r, 0)) > 0:
                strs.append(f"{r.value} {qty}")
        return " ".join(strs)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Show reactions on open issues & PRs in your GitHub repositories"
    )
    parser.parse_args()
    with Client(token=get_ghtoken()) as client:
        for repo in client.get_repositories():
            for issue in client.get_issue_reactions(repo):
                if issue.has_reactions():
                    print("Issue:" if not issue.is_pr else "PR:", issue.title)
                    print("URL:", issue.url)
                    print("Reactions:", issue.reaction_str())
                    print()


if __name__ == "__main__":
    main()
