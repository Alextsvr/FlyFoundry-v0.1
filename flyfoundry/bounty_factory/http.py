"""Polite HTTP: identifiable user agent, robots.txt check, minimum interval, retry with exponential backoff, time budget."""
from __future__ import annotations

import time
import urllib.parse
import urllib.robotparser
from typing import Callable

from flyfoundry.phase1.probes import urllib_transport

USER_AGENT = "flyfoundry-bounty/0.2 (+https://github.com/Alextsvr/FlyFoundry-v0.1; public pages only, rate-limited)"


class BudgetExceeded(RuntimeError):
    pass


class HostBlocked(RuntimeError):
    pass


class RobotsDenied(RuntimeError):
    pass


class Fetcher:
    def __init__(self, transport: Callable | None = None, min_interval: float = 2.0, retries: int = 3,
                 backoff: float = 2.0, max_seconds: float = 600.0, sleep=time.sleep, clock=time.monotonic):
        self.transport = transport or urllib_transport
        self.min_interval, self.retries, self.backoff = min_interval, retries, backoff
        self.max_seconds, self.sleep, self.clock = max_seconds, sleep, clock
        self.t0 = clock()
        self._last = None
        self.requests = 0
        self._robots: dict = {}
        self.denied_hosts: set = set()   # hosts that answered 401/403: never retried or bypassed in this run

    def _pace(self):
        if self._last is not None:
            wait = self.min_interval - (self.clock() - self._last)
            if wait > 0:
                self.sleep(wait)
        self._last = self.clock()

    def get(self, url: str, accept: str = "*/*"):
        """Returns (status, body). Retries on transport failure (0), 429 and 5xx. Other statuses are returned as data."""
        status, body = 0, ""
        for attempt in range(self.retries + 1):
            if self.clock() - self.t0 > self.max_seconds:
                raise BudgetExceeded(f"time budget {self.max_seconds}s exhausted before {url}")
            self._pace()
            self.requests += 1
            status, body = self.transport(url, {"User-Agent": USER_AGENT, "Accept": accept})
            if status == 0 or status == 429 or status >= 500:
                if attempt < self.retries:
                    self.sleep(self.backoff ** (attempt + 1))
                    continue
            return status, body
        return status, body

    def allowed(self, url: str) -> bool:
        """robots.txt check (cached per host). 404 = allow all; any other failure = refuse (conservative)."""
        p = urllib.parse.urlsplit(url)
        host = f"{p.scheme}://{p.netloc}"
        if host not in self._robots:
            status, body = self.get(host + "/robots.txt", "text/plain")
            rp = urllib.robotparser.RobotFileParser()
            if status == 200:
                rp.parse(body.splitlines())
                self._robots[host] = rp
            elif status in (404, 410):
                rp.parse([])
                self._robots[host] = rp
            else:
                self._robots[host] = None
        rp = self._robots[host]
        return bool(rp and rp.can_fetch(USER_AGENT, url))

    def get_checked(self, url: str, accept: str = "*/*"):
        host = urllib.parse.urlsplit(url).netloc
        if host in self.denied_hosts:
            raise HostBlocked(f"{host} already answered 401/403 in this run; not retrying or bypassing")
        if not self.allowed(url):
            raise RobotsDenied(f"robots.txt does not allow (or could not be read for) {url}")
        status, body = self.get(url, accept)
        if status in (401, 403):
            self.denied_hosts.add(host)
        return status, body
