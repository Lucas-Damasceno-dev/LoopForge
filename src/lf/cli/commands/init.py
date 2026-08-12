import click
from rich.console import Console

from lf.config.loader import save_config
from lf.config.schema import LoopForgeConfig, resolve_tech_stack
from lf.pipeline.llm_factory import resolve_default_model

console = Console()


@click.command(name="init")
@click.option("--name", default="LoopForge Project", help="Project name")
@click.option("--stack", default="python", help="Primary tech stack language")
@click.option("--framework", default=None, help="Primary framework")
@click.option("--llm-provider", default=None, help="LLM provider (google/openrouter/ollama)")
@click.option("--llm-model", default=None, help="LLM model name")
@click.option("--budget", default=10.0, type=float, help="Max budget in USD per run")
@click.option("--ontology", default="examples/the-foundry", help="Path to ontology directory (The Foundry)")
def init_cmd(
    name: str,
    stack: str,
    framework: str | None,
    llm_provider: str | None,
    llm_model: str | None,
    budget: float,
    ontology: str,
):
    """Initialize a new LoopForge v6 project configuration."""
    # Fix 2: fonte única do modelo default — resolve_default_model() aplica a
    # precedência env (OPENROUTER_MODEL → OPENCODE_MODEL) → config
    # .loopforge.json → constante canônica (antes havia default divergente
    # hardcoded aqui).
    provider_to_use = llm_provider or "openrouter"
    model_to_use = llm_model or resolve_default_model()

    resolved_stack = resolve_tech_stack(stack, framework)

    cfg = LoopForgeConfig(
        project_id=name.lower().replace(" ", "_"),
        project_name=name,
        stack=resolved_stack,
        llm_provider=provider_to_use,
        llm_model=model_to_use,
        budget_limit_usd=budget,
        ontology_path=ontology,
    )
    p = save_config(cfg)
    console.print(f"[bold green]Initialized LoopForge project config at {p}[/bold green]")
    console.print(
        f"  [cyan]Stack:[/cyan] {resolved_stack.language}/{resolved_stack.framework} ({resolved_stack.testing_harness}/{resolved_stack.package_manager})"
    )
    console.print(f"  [cyan]LLM:[/cyan] {provider_to_use}/{model_to_use}")
    console.print(f"  [cyan]Budget:[/cyan] ${budget:.2f} USD")
    console.print(f"  [cyan]Ontology:[/cyan] {ontology}")
