use clap::{Parser, Subcommand};

#[derive(Parser)]
#[command(name = "git-pet")]
#[command(about = "A virtual pet that lives in your terminal and thrives on your commits")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Create a new pet and give it a name
    Init { name: String },
    /// Show your pet's current mood, art and status
    Status,
    /// Feed your pet to reduce its hunger
    Feed,
    /// Display detailed commit and pet statistics
    Stats,
    /// Register a new commit event (used by the git hook)
    CommitEvent,
    /// Install the global git hook for automatic commit tracking
    Setup,
}

fn main() -> anyhow::Result<()> {
    let cli = Cli::parse();

    match cli.command {
        Commands::Init { name } => git_pet::commands::init::execute(name)?,
        Commands::Status => git_pet::commands::status::execute()?,
        Commands::Feed => git_pet::commands::feed::execute()?,
        Commands::Stats => git_pet::commands::stats::execute()?,
        Commands::CommitEvent => git_pet::commands::commit_event::execute()?,
        Commands::Setup => git_pet::commands::setup::execute()?,
    }

    Ok(())
}