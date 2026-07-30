"""Pydantic models para o schema do Agentic Interface Registry."""

from typing import List, Optional
from pydantic import BaseModel, Field


class ConsumerInfo(BaseModel):
    file: str
    line: int = 1
    agent: str = "unknown"


class InterfaceHistory(BaseModel):
    version: str = "1.0.0"
    signature: str
    agent: str = "developer"
    commit: str = "HEAD"


class InterfaceItem(BaseModel):
    id: str
    kind: str  # function, class, interface, type, api
    name: str
    module: str
    signature: str
    exported: bool = True
    tags: List[str] = Field(default_factory=list)
    consumers: List[ConsumerInfo] = Field(default_factory=list)
    history: List[InterfaceHistory] = Field(default_factory=list)
    last_modified: str = ""
    last_agent: str = "developer"


class BreakingChange(BaseModel):
    interface_id: str
    interface_name: str
    module: str
    change_type: str  # parameter_added_without_default, parameter_removed, signature_changed
    details: str
    impacted_consumers: List[ConsumerInfo] = Field(default_factory=list)
    detected_at: str = ""


class RegistrySchema(BaseModel):
    version: str = "1.0.0"
    interfaces: List[InterfaceItem] = Field(default_factory=list)
    breaking_changes: List[BreakingChange] = Field(default_factory=list)
