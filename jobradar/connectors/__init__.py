"""One connector per job system, all with the same shape:

    async def fetch(board: Board, client: HttpClient, ctx: FetchContext) -> FetchResult

A connector returns every job on the board (all countries) with parsed
locations; the scanner decides which ones to store.
"""

from __future__ import annotations

from . import (
    ashby,
    bamboohr,
    breezy,
    greenhouse,
    humi,
    jazzhr,
    lever,
    pinpoint,
    recruitee,
    rippling,
    smartrecruiters,
    successfactors,
    teamtailor,
    workable,
    workday,
)
from ._common import FetchContext, FetchResult

CONNECTORS = {
    "greenhouse": greenhouse.fetch,
    "lever": lever.fetch,
    "ashby": ashby.fetch,
    "smartrecruiters": smartrecruiters.fetch,
    "workable": workable.fetch,
    "recruitee": recruitee.fetch,
    "breezy": breezy.fetch,
    "rippling": rippling.fetch,
    "bamboohr": bamboohr.fetch,
    "workday": workday.fetch,
    "successfactors": successfactors.fetch,
    "jazzhr": jazzhr.fetch,
    "pinpoint": pinpoint.fetch,
    "teamtailor": teamtailor.fetch,
    "humi": humi.fetch,
}

__all__ = ["CONNECTORS", "FetchContext", "FetchResult"]
