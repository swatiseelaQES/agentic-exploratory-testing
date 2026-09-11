from typing import Literal

from pydantic import BaseModel, Field


ActionName = Literal[
    "click",
    "type",
    "clear",
    "select",
    "navigate",
    "back",
    "refresh",
    "inspect",
    "finish",
]


class Target(BaseModel):
    ref: str | None = Field(
        default=None,
        description=(
            "Exact element reference supplied in the current observation, "
            "such as element-7"
        ),
    )
    role: str | None = None
    name: str | None = None
    css: str | None = None


class CandidateFinding(BaseModel):
    finding_key: str = Field(
        description=(
            "Stable lower_snake_case identifier reused whenever "
            "this finding is updated"
        )
    )
    title: str
    status: Literal["suspicion", "investigating", "reproduced"]
    expected: str
    actual: str
    confidence: Literal["low", "medium", "high"]

    causal_explanation: str | None = None
    causal_status: Literal[
        "not_claimed",
        "inferred",
        "verified",
    ] = "not_claimed"

    evidence_steps: list[int] = Field(default_factory=list)
    reproduction: list[str] = Field(default_factory=list)


class AgentDecision(BaseModel):
    action: ActionName
    target: Target | None = None
    value: str | None = None

    reason: str
    hypothesis: str | None = None
    expected_observation: str | None = None

    coverage_area: str | None = Field(
        default=None,
        description="Charter focus area advanced by this action",
    )
    learned: str | None = Field(
        default=None,
        description=(
            "Concise new information established by the current observation"
        ),
    )

    finding: CandidateFinding | None = None


class Observation(BaseModel):
    url: str
    title: str
    visible_text: str
    elements: list[dict]
    screenshot: str | None = None