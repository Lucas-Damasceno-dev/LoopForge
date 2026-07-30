use anyhow::{Context, Result};
use crate::state::{load_state, save_state};
use chrono::Utc;

pub fn execute() -> Result<()> {
    let mut state = load_state()?.context("No pet found. Please init first.")?;
    let pet = &mut state.pet;

    let today = Utc::now().date_naive();

    if let Some(last_commit) = pet.last_commit_date {
        let days_diff = (today - last_commit).num_days();
        if days_diff == 1 {
            pet.streak += 1;
        } else if days_diff > 1 {
            pet.streak = 1;
        }
        // same day → no streak change
    } else {
        pet.streak = 1;
    }

    let xp_gain = 10 + (pet.streak * 2);
    pet.xp += xp_gain;
    pet.commit_count += 1;
    pet.last_commit_date = Some(today);
    pet.hunger = (pet.hunger + 10).min(100);

    pet.maybe_evolve();

    save_state(&state).context("Failed to save state")?;
    println!("Commit registered! +{} XP", xp_gain);
    Ok(())
}