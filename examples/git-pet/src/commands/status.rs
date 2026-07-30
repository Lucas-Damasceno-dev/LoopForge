use anyhow::{Context, Result};
use crate::state::load_state;
use crate::ascii_art;
use colored::Colorize;

pub fn execute() -> Result<()> {
    let state = load_state()?.context("No pet found. Use 'git-pet init <name>' to create one.")?;
    let pet = &state.pet;
    let mood = pet.calculate_mood();
    let stage = pet.current_stage();
    let art = ascii_art::get_art(&pet.species, &stage, &mood);

    let colored_art = match mood.as_str() {
        "happy" => art.green(),
        "sad" => art.blue(),
        "sick" => art.red(),
        "neutral" => art.yellow(),
        _ => art.normal(),
    };
    println!("{}", colored_art);

    println!("{} the {} ({} {})", pet.name.green(), pet.species, stage, mood);
    println!("XP: {}/{}", pet.xp, pet.xp_for_next_level());
    println!("Hunger: {}", pet.hunger);
    println!("Streak: {} days", pet.streak);
    Ok(())
}