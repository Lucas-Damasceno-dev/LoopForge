import click
from rich.console import Console

from lf.config.loader import save_config
from lf.config.schema import LoopForgeConfig, TechStack

console = Console()


@click.command(name="init")
@click.option("--name", default="LoopForge Project", help="Project name")
@click.option("--stack", default="python", help="Primary tech stack language")
@click.option("--framework", default="fastapi", help="Primary framework")
@click.option("--llm-provider", default="google", help="LLM provider (google/ollama/openrouter)")
@click.option("--llm-model", default="gemini-1.5-flash", help="LLM model name")
@click.option("--budget", default=10.0, type=float, help="Max budget in USD per run")
@click.option("--ontology", default="examples/the-foundry", help="Path to ontology directory (The Foundry)")
def init_cmd(name: str, stack: str, framework: str, llm_provider: str, llm_model: str, budget: float, ontology: str):
    """Initialize a new LoopForge v6 project configuration."""
    cfg = LoopForgeConfig(
        project_id=name.lower().replace(" ", "_"),
        project_name=name,
        stack=TechStack(language=stack, framework=framework),
        llm_provider=llm_provider,
        llm_model=llm_model,
        budget_limit_usd=budget,
        ontology_path=ontology,
    )
    p = save_config(cfg)
    console.print(f"[bold green]Initialized LoopForge project config at {p}[/bold green]")
    console.print(f"  [cyan]Stack:[/cyan] {stack}/{framework}")
    console.print(f"  [cyan]LLM:[/cyan] {llm_provider}/{llm_model}")
    console.print(f"  [cyan]Budget:[/cyan] ${budget:.2f} USD")
    console.print(f"  [cyan]Ontology:[/cyan] {ontology}")
