"""Pydantic models para o schema do Codebase Genome."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class LanguageStats(BaseModel):
    files: int = 0
    lines: int = 0


class RepoMetadata(BaseModel):
    root: str
    langs: Dict[str, LanguageStats] = Field(default_factory=dict)
    total_files: int = 0
    total_lines: int = 0


class ConventionDetail(BaseModel):
    pattern: str
    lib: Optional[str] = None
    usage_rate: float = 1.0


class Conventions(BaseModel):
    error_handling: Optional[ConventionDetail] = None
    testing: Optional[Dict[str, str]] = None
    custom: Dict[str, Any] = Field(default_factory=dict)


class Symbol(BaseModel):
    name: str
    kind: str  # function, class, interface, type, variable
    line: int = 1
    exported: bool = True
    signature: Optional[str] = None


class ModuleInfo(BaseModel):
    path: str
    language: str
    exports: List[Symbol] = Field(default_factory=list)
    imports: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    dependents: List[str] = Field(default_factory=list)
    instability: float = 0.0
    lines_count: int = 0


class LayerViolation(BaseModel):
    from_path: str
    to_path: str
    type: str = "illegal-boundary"


class HighRiskFile(BaseModel):
    path: str
    dependents: int
    owners: int = 1


class BusFactor(BaseModel):
    score: float = 1.0
    high_risk_files: List[HighRiskFile] = Field(default_factory=list)


class Architecture(BaseModel):
    pattern: str = "custom"
    source: str = ".genomerc"
    layers: List[str] = Field(default_factory=list)
    layer_violations: List[LayerViolation] = Field(default_factory=list)
    circular_deps: List[List[str]] = Field(default_factory=list)
    bus_factor: BusFactor = Field(default_factory=BusFactor)


class Genome(BaseModel):
    version: str = "1.0.0"
    repo: RepoMetadata
    conventions: Conventions = Field(default_factory=Conventions)
    modules: List[ModuleInfo] = Field(default_factory=list)
    architecture: Architecture = Field(default_factory=Architecture)
    generated_at: str
    ttl_seconds: int = 86400
