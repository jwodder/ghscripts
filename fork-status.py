#!/usr/bin/env -S pipx run
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "click >= 7.0",
#     "ghrepo ~= 0.1",
#     "ghtoken ~= 0.1",
#     "PyGithub ~= 2.0",
# ]
# ///

from __future__ import annotations
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from operator import attrgetter
import click
from ghrepo import get_local_repo
from ghtoken import get_ghtoken
from github import Auth, Github, GithubException
from github.Repository import Repository


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--all", "list_all", is_flag=True)
@click.option("-B", "--all-branches", is_flag=True)
@click.option("--has-pr/--no-pr", default=None)
@click.option("--pr-status", type=click.Choice(["open", "closed", "merged"]))
@click.argument("repo", nargs=-1)
def main(
    repo: tuple[str, ...],
    list_all: bool,
    all_branches: bool,
    has_pr: bool | None,
    pr_status: str | None,
) -> None:
    gh = Github(auth=Auth.Token(get_ghtoken()))
    repo_objs: Iterable[Repository]
    if list_all:
        repo_objs = filter(
            attrgetter("fork"), gh.get_user().get_repos(affiliation="owner")
        )
    elif repo:
        repo_objs = map(gh.get_repo, repo)
    else:
        repo_objs = [gh.get_repo(str(get_local_repo()))]
    for i, r in enumerate(repo_objs):
        if i:
            print()
        header = f"{r.full_name} → {r.parent.full_name}"
        print(header)
        print("-" * len(header))
        any_branches = False
        for brstatus in get_branch_statuses(r):
            if brstatus.is_even() and not all_branches:
                continue
            if pr_status is not None and pr_status != brstatus.prstatus:
                continue
            if has_pr is True and brstatus.prnum is None:
                continue
            if has_pr is False and brstatus.prnum is not None:
                continue
            any_branches = True
            print(brstatus.show())
        if not any_branches:
            print("-- nothing --")


@dataclass
class BranchStatus:
    name: str
    on_parent: bool
    related: bool
    ahead: int | None
    behind: int | None
    prnum: int | None
    prstatus: str | None

    def is_even(self) -> bool:
        return self.on_parent and self.ahead == 0 and self.behind == 0

    def ahead_behind(self) -> str:
        if not self.related:
            return "NO RELAT"
        elif self.ahead or self.behind:
            s = ""
            if self.ahead:
                s += f"+{self.ahead}"
                if self.behind:
                    s += "/"
            if self.behind:
                s += f"-{self.behind}"
            return s
        else:
            return "="

    def show(self) -> str:
        plus = " " if self.on_parent else "+"
        if self.prnum is not None:
            assert self.prstatus is not None
            prnum = f"#{self.prnum}"
            prstatus = self.prstatus.upper()
        else:
            prnum = ""
            prstatus = ""
        return f"{plus} {self.name:32}  {self.ahead_behind():9}  {prnum:8}  {prstatus}"


def get_branch_statuses(repo: Repository) -> Iterator[BranchStatus]:
    for br in sorted(repo.get_branches(), key=attrgetter("name")):
        try:
            repo.parent.get_branch(br.name)
        except GithubException as e:
            if e.status == 404:
                on_parent = False
                cmpbranch = repo.parent.default_branch
            else:
                raise
        else:
            on_parent = True
            cmpbranch = br.name
        try:
            delta = repo.compare(f"{repo.parent.owner.login}:{cmpbranch}", br.name)
        except GithubException as e:
            if e.status == 404:
                # No common ancester between branches (or other causes?)
                related = False
                ahead = None
                behind = None
            else:
                raise
        else:
            related = True
            ahead = delta.ahead_by
            behind = delta.behind_by
        try:
            pr = next(
                iter(
                    repo.parent.get_pulls(
                        head=f"{repo.full_name}:{br.name}",
                        # We need to include the full name in the `head` for
                        # the cases where one of the repositories has been
                        # renamed, in which case just doing
                        # `f"{repo.owner.login}:{br.name}"` will return an
                        # empty list.  The ability to use the full name in the
                        # `head` isn't even documented!
                        sort="created",
                        direction="desc",
                        state="all",
                    )
                )
            )
        except StopIteration:
            prnum = None
            prstatus = None
        else:
            prnum = pr.number
            prstatus = "merged" if pr.merged_at is not None else pr.state
        yield BranchStatus(
            name=br.name,
            on_parent=on_parent,
            related=related,
            ahead=ahead,
            behind=behind,
            prnum=prnum,
            prstatus=prstatus,
        )


if __name__ == "__main__":
    main()
