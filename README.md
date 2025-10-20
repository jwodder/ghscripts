[![Project Status: Concept – Minimal or no implementation has been done yet, or the repository is only intended to be a limited example, demo, or proof-of-concept.](https://www.repostatus.org/badges/latest/concept.svg)](https://www.repostatus.org/#concept)
[![MIT License](https://img.shields.io/github/license/jwodder/ghscripts.svg)](https://opensource.org/licenses/MIT)

This repository contains assorted minor Python scripts for doing things via the
GitHub REST & GraphQL APIs.  The dependencies for each script (including the
minimum required Python version) are specified at the top of each file via
[inline script metadata][].  To install a given script, simply copy it into a
directory in your `PATH` and, if necessary, change the shebang line to invoke
your preferred consumer of inline script metadata.

[inline script metadata]: https://packaging.python.org/en/latest/specifications/inline-script-metadata/

Scripts
=======

Each script requires a GitHub access token with appropriate permissions in
order to run.  Specify the token via the `GH_TOKEN` or `GITHUB_TOKEN`
environment variable (possibly in an `.env` file), by storing a token with the
`gh` or `hub` command, or by setting the `hub.oauthtoken` Git config option in
your `~/.gitconfig` file.

In the below descriptions, "your user account" is the GitHub account to which
the GitHub access token belongs.

Run a given script with the `-h` or `--help` option for more information.

- `contribs.py` — Show a table of the number of commits per repository per day
  that your user account has made to GitHub repositories over the past several
  days

- `creations.py` — List various actions performed by your user account since a
  given date.

  The types of actions shown are:

  - Creating a repository
  - Forking a repository
  - Opening, closing, or reopening an issue or pull request
  - Publishing a release

- `fork-status.py` — For each GitHub repository in a given set of forks, print
  all branches that differ from the parent repository along with the
  corresponding PR number and PR status, if any

- `gh-rate-limit.py` — For each rate-limited GitHub API resource in your user
  account that is not at "full," show the number of resources used, remaining,
  & total and the timestamp at which the usage will reset

- `reactions.py` — List all issues & PRs in repositories owned by your user
  account that people have reacted to

- `viewpr.py` — Determine the GitHub pull request created from the current
  branch in the Git repository in the current working directory and open it in
  a web browser

See Also
========

You may also be interested in the following fuller-fledged programs of mine for
interacting with the GitHub API:

- [dependalabels](https://github.com/jwodder/dependalabels)
- [forklone](https://github.com/jwodder/forklone)
- [labelmaker](https://github.com/jwodder/labelmaker)
- [mkissues](https://github.com/jwodder/mkissues)
- [repolist](https://github.com/jwodder/repolist)
