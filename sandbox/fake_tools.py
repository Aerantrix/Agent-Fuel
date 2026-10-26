"""Fake external tools with controllable failure modes.

Nothing here touches a real service. Each tool reads its failure mode from the
scenario being run and misbehaves accordingly, so every scenario is reproducible
and costs nothing but the agent's own tokens.
"""

import time
from dataclasses import dataclass, field


class ToolError(Exception):
    """Base class so the error classifier has something to match on."""

    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


class ConnectionFailed(ToolError):
    pass


class AuthFailed(ToolError):
    pass


class Timeout(ToolError):
    pass


# Canned payloads. Small on purpose: the experiment measures the agent's token
# use, not the size of the fixtures.
GOOD_METRICS = {
    "domain": "example.com",
    "period": "30d",
    "organic_traffic": 128_400,
    "backlinks": 9_312,
    "keywords": 4_118,
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
        timeout        slow, then a timeout error          (scenario 4)
        partial        truncated page, cursor never moves  (scenario 5)
        flapping       alternates success and failure      (scenario 6)
        slow_degrade   correct, but slower every call      (scenario 7)
        malformed      HTML where JSON was expected        (scenario 8)
        slow_healthy   correct, consistently slow          (scenario 14)
    """

    failure_mode: str = "healthy"
    healthy_calls_first: int = 0  # let N calls succeed before breaking
    sleep_enabled: bool = False   # set False in CI so runs stay fast
    calls: int = 0
    log: list = field(default_factory=list)

    def _sleep(self, seconds):
        if self.sleep_enabled:
            time.sleep(seconds)

    def get_metrics(self, domain, period="30d"):
        self.calls += 1
        self.log.append((self.calls, domain, period))

        if self.calls <= self.healthy_calls_first:
            return dict(GOOD_METRICS, domain=domain, period=period)

        mode = self.failure_mode

        if mode == "healthy":
            return dict(GOOD_METRICS, domain=domain, period=period)

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
            return dict(PARTIAL_METRICS, domain=domain, period=period)

        if mode == "flapping":
            if self.calls % 2 == 1:
                return dict(GOOD_METRICS, domain=domain, period=period)
            raise ConnectionFailed("Service unavailable")

        if mode == "slow_degrade":
            self._sleep(min(self.calls * 0.5, 10))
            return dict(GOOD_METRICS, domain=domain, period=period)

        if mode == "malformed":
            return MALFORMED_BODY

        if mode == "slow_healthy":
            self._sleep(1.5)
            return dict(GOOD_METRICS, domain=domain, period=period)

        raise ValueError(f"unknown failure_mode: {mode}")


@dataclass
class FakeSecondSource:
    """A second metrics source, used only by scenario 10.

    Returns values that contradict FakeAnalytics so the agent has a conflict to
    chase. Nothing is broken: the agent spends because reconciling is expensive.
    """

    disagree: bool = True
    calls: int = 0

    def get_metrics(self, domain, period="30d"):
        self.calls += 1
        traffic = 61_900 if self.disagree else GOOD_METRICS["organic_traffic"]
        return {
            "domain": domain,
            "period": period,
            "organic_traffic": traffic,
            "source": "second_source",
        }


def build_tools(scenario):
    """Assemble the tool set a scenario needs.

    scenario is one entry from evaluation/scenarios.json.
    """
    mode = scenario["failure_mode"]
    tools = {"analytics": FakeAnalytics(failure_mode=mode)}

    if scenario["slug"] == "conflicting_data":
        tools["analytics"] = FakeAnalytics(failure_mode="healthy")
        tools["second_source"] = FakeSecondSource(disagree=True)

    return tools
