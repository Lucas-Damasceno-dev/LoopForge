use anyhow::{Context, Result};
use crate::state::load_state;

pub fn execute() -> Result<()> {
    let state = load_state()?.context("No pet found.")?;
    let pet = &state.pet;

    println!("=== {} Stats ===", pet.name);
    println!("Species: {}", pet.species);
    println!("Stage: {}", pet.current_stage());
    println!("XP: {}/{}", pet.xp, pet.xp_for_next_level());
    println!("Hunger: {}", pet.hunger);
    println!("Mood: {}", pet.calculate_mood());
    println!("Commits: {}", pet.commit_count);
    println!("Streak: {} days", pet.streak);
    println!("Total XP: {}", pet.xp);
    Ok(())
}