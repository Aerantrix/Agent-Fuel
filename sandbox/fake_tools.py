"""Fake external tools with controllable failure modes.

Nothing here touches a real service. Each tool reads its failure mode from the
scenario being run and misbehaves accordingly, so every scenario is reproducible
and costs nothing but the agent's own tokens.
"""

import hashlib
import time
from dataclasses import dataclass, field


class ToolError(Exception):
    """Base class so the error classifier has something to match on."""

    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


# The fourth condition: the same base prompt, but the service's transient
# errors carry the advice real services often give. Off by default, so the
# prompt levels differ in the prompt alone; AGENT_FUEL_ERROR_HINT=on adds
# the sentence to connection failures and timeouts, never to a 401.
import os as _os
ERROR_HINT = ". Please try again later." if _os.environ.get("AGENT_FUEL_ERROR_HINT", "off") == "on" else ""


class ConnectionFailed(ToolError):
    def __init__(self, message, status=None):
        super().__init__(message + ERROR_HINT, status)


class AuthFailed(ToolError):
    pass


class Timeout(ToolError):
    def __init__(self, message, status=None):
        super().__init__(message + ERROR_HINT, status)


# Canned payloads. Small on purpose: the experiment measures the agent's token
# use, not the size of the fixtures.
def good_metrics(domain, period):
    """Healthy metrics for one domain and period.

    The numbers differ from domain to domain and never from run to run. An
    earlier version returned one payload for every domain, and an agent
    ranking ten sites noticed they were identical and quit. See
    docs/work_log.md.
    """
    seed = int(hashlib.sha1(f"{domain}|{period}".lower().encode("utf-8")).hexdigest(), 16)
    return {
        "domain": domain,
        "period": period,
        "organic_traffic": 20_000 + seed % 180_000,
        "backlinks": 1_000 + (seed >> 20) % 19_000,
        "keywords": 500 + (seed >> 40) % 7_500,
        "truncated": False,
    }


PARTIAL_METRICS = {
    "domain": "example.com",
    "period": "30d",
    "rows_returned": 20,
    "rows_total": 500,
    "truncated": True,
    "next_cursor": "page_2",  # the cursor never advances in scenario 5
}

MALFORMED_BODY = (
    "<html><head><title>502 Bad Gateway</title></head>"
    "<body><h1>502 Bad Gateway</h1><p>nginx</p></body></html>"
)


@dataclass
class FakeAnalytics:
    """Stands in for an analytics API such as Ahrefs.

    failure_mode is one of:
        healthy        normal responses
        unavailable    connection error on every call      (scenario 1)
        empty          valid response, zero records        (scenario 2)
        auth           401 on every call                   (scenario 3)
        timeout        a timeout error on every call       (scenario 4)
        partial        truncated page, cursor never moves  (scenario 5)
        flapping       alternates success and failure      (scenario 6)
        malformed      HTML where JSON was expected        (scenario 8)
    """

    failure_mode: str = "healthy"
    healthy_calls_first: int = 0  # let N calls succeed before breaking
    sleep_enabled: bool = False   # set False in CI so runs stay fast
    calls: int = 0
    log: list = field(default_factory=list)

    def _sleep(self, seconds):
        if self.sleep_enabled:
            time.sleep(seconds)

    def get_metrics(self, domain, period="30d", cursor=None):
        self.calls += 1
        self.log.append((self.calls, domain, period, cursor))

        if self.calls <= self.healthy_calls_first:
            return good_metrics(domain, period)

        mode = self.failure_mode

        if mode == "healthy":
            return good_metrics(domain, period)

        if mode == "unavailable":
            raise ConnectionFailed("Service unavailable")

        if mode == "empty":
            return {"domain": domain, "period": period, "results": []}

        if mode == "auth":
            raise AuthFailed("Invalid or expired credentials", status=401)

        if mode == "timeout":
            self._sleep(2)
            raise Timeout("Request timed out after 30s", status=504)

        if mode == "partial":
            # Whatever cursor the agent sends, the same first page comes back.
            return dict(PARTIAL_METRICS, domain=domain, period=period)

        if mode == "flapping":
            if self.calls % 2 == 1:
                return good_metrics(domain, period)
            raise ConnectionFailed("Service unavailable")

        if mode == "malformed":
            return MALFORMED_BODY

        raise ValueError(f"unknown failure_mode: {mode}")


def build_tools(scenario):
    """Assemble the tool set a scenario needs.

    scenario is one entry from evaluation/scenarios.json.
    """
    return {"analytics": FakeAnalytics(failure_mode=scenario["failure_mode"])}
