#!/usr/bin/env -S pipx run
# /// script
# requires-python = ">=3.11"
# dependencies = ["ghreq ~= 0.1", "ghtoken ~= 0.1"]
# ///

from __future__ import annotations
from datetime import datetime, timezone
from ghreq import Client
from ghtoken import get_ghtoken

with Client(token=get_ghtoken()) as client:
    data = client.get("/rate_limit")
    any_used = False
    for k, v in data["resources"].items():
        if v["used"]:
            any_used = True
            reset = datetime.fromtimestamp(v["reset"], timezone.utc).astimezone()
            print(
                f"{k}: {v['used']} / {v['limit']} used; {v['remaining']} left;"
                f" reset at {reset}"
            )
    if not any_used:
        print("No rate-limited API requests used")
