use anyhow::{Context, Result};
use crate::state::{load_state, save_state};

pub fn execute() -> Result<()> {
    let mut state = load_state()?.context("No pet found.")?;
    state.pet.hunger = 0;
    save_state(&state).context("Failed to save state")?;
    println!("Your pet has been fed and is happy!");
    Ok(())
}