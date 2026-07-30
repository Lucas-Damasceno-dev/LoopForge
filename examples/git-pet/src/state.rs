use anyhow::{Context, Result};
use std::fs;
use std::path::PathBuf;
use serde::{Deserialize, Serialize};

use crate::pet::Pet;

#[derive(Debug, Serialize, Deserialize)]
pub struct State {
    pub pet: Pet,
}

fn state_path() -> Result<PathBuf> {
    let base = dirs::data_dir().context("Cannot determine data directory")?;
    let dir = base.join("git-pet");
    fs::create_dir_all(&dir).context("Failed to create data directory")?;
    Ok(dir.join("state.json"))
}

pub fn load_state() -> Result<Option<State>> {
    let path = state_path()?;
    if !path.exists() {
        return Ok(None);
    }
    let content = fs::read_to_string(&path).context("Failed to read state file")?;
    let state: State = serde_json::from_str(&content).context("Failed to parse state JSON")?;
    Ok(Some(state))
}

pub fn save_state(state: &State) -> Result<()> {
    let path = state_path()?;
    let content = serde_json::to_string_pretty(state).context("Failed to serialize state")?;
    fs::write(&path, content).context("Failed to write state file")?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    fn setup_env() -> TempDir {
        let tmp = TempDir::new().unwrap();
        let data_home = tmp.path().join("data");
        std::fs::create_dir_all(&data_home).unwrap();
        std::env::set_var("XDG_DATA_HOME", &data_home);
        tmp
    }

    #[test]
    fn test_load_no_state() {
        let _tmp = setup_env();
        let result = load_state();
        assert!(result.is_ok());
        assert!(result.unwrap().is_none());
    }

    #[test]
    fn test_save_and_load() {
        let _tmp = setup_env();
        let pet = Pet::new("TestPet".to_string(), "Dragon".to_string());
        let state = State { pet };
        save_state(&state).unwrap();
        let loaded = load_state().unwrap().unwrap();
        assert_eq!(loaded.pet.name, "TestPet");
        assert_eq!(loaded.pet.species, "Dragon");
    }
}