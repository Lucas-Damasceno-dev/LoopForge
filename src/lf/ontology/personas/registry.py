from dataclasses import dataclass, field


@dataclass
class AgentProfile:
    id: str
    role: str
    mission: str
    responsibilities: list[str] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)


class PersonaRegistry:
    def __init__(self):
        self._profiles: dict[str, AgentProfile] = {
            "cpo": AgentProfile(
                id="cpo",
                role="Chief Product Officer",
                mission="Transform business vision into structured product Epics and high-level strategy.",
                responsibilities=["Define epics", "Prioritize roadmap", "Align business vision"],
                tools=["llm"],
            ),
            "pm": AgentProfile(
                id="pm",
                role="Product Manager",
                mission="Decompose Epics into granular User Stories with strict acceptance criteria.",
                responsibilities=["Create user stories", "Validate acceptance criteria", "Maintain backlog"],
                tools=["llm", "artifact_validator"],
            ),
            "tech_lead": AgentProfile(
                id="tech_lead",
                role="Tech Lead",
                mission="Design technical specification, architecture, stack choices, and task DAG.",
                responsibilities=["Draft tech spec", "Define system architecture", "Guide implementation"],
                tools=["llm", "tech_spec_builder"],
            ),
            "developer": AgentProfile(
                id="developer",
                role="Developer",
                mission="Write clean, modular code that passes tests using OpenCode execution engine.",
                responsibilities=["Implement features", "Fix bugs", "Execute OpenCode"],
                tools=["opencode", "git_sandbox"],
            ),
            "qa": AgentProfile(
                id="qa",
                role="Quality Assurance Engineer",
                mission="Execute test suite, analyze regressions, and verify bug fixes.",
                responsibilities=["Run test harness", "Generate test execution report", "Flag regressions"],
                tools=["test_harness", "artifact_validator"],
            ),
            "appsec": AgentProfile(
                id="appsec",
                role="Application Security Lead",
                mission="Audit code for security vulnerabilities, secrets leakage, and OWASP issues.",
                responsibilities=["Run security scanner", "Flag vulnerabilities"],
                tools=["security_scanner"],
            ),
            "devops": AgentProfile(
                id="devops",
                role="DevOps Specialist",
                mission="Manage build pipelines, CI/CD integrations, and release tags.",
                responsibilities=["Configure CI", "Create release PRs"],
                tools=["git_pr", "checkpoint"],
            ),
        }

    def get_profile(self, agent_id: str) -> AgentProfile | None:
        return self._profiles.get(agent_id.lower())

    def resolve(self, agent_id: str) -> AgentProfile:
        profile = self.get_profile(agent_id)
        if not profile:
            return AgentProfile(
                id=agent_id,
                role=agent_id.capitalize(),
                mission=f"Execute task as {agent_id}",
                responsibilities=[],
                tools=[],
            )
        return profile


registry = PersonaRegistry()
