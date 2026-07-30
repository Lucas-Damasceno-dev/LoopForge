use anyhow::{Context, Result};
use rand::Rng;
use crate::state::{load_state, save_state, State};
use crate::pet::Pet;

pub fn execute(name: String) -> Result<()> {
    if let Ok(Some(_)) = load_state() {
        anyhow::bail!("A pet already exists. Please remove ~/.local/share/git-pet/state.json or equivalent to reset.");
    }

    let species = random_species();
    let pet = Pet::new(name, species);
    let state = State { pet };
    save_state(&state).context("Failed to save pet state")?;
    println!("A new pet has been created! 🐣");
    println!("Name: {}", state.pet.name);
    println!("Species: {}", state.pet.species);
    Ok(())
}

fn random_species() -> String {
    let species = vec!["Cat", "Dog", "Dragon", "Fox", "Whale"];
    let idx = rand::thread_rng().gen_range(0..species.len());
    species[idx].to_string()
}