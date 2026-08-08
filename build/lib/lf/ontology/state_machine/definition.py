from enum import StrEnum


class TaskState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    VALIDATING = "validating"
    FAILED = "failed"
    DONE = "done"


class PipelineNode(StrEnum):
    CPO = "cpo"
    PM = "pm"
    TECH_LEAD = "tech_lead"
    DEVELOPER = "developer"
    QA = "qa"
    APPSEC = "appsec"
    DEVOPS = "devops"
    ROUTER = "router"
