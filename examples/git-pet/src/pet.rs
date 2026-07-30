use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct Pet {
    pub name: String,
    pub species: String,
    pub stage: String, // "Egg", "Baby", "Child", "Adult", "Elder"
    pub xp: u64,
    pub hunger: u64, // 0–100, 0 = full, 100 = starving
    pub last_commit_date: Option<chrono::NaiveDate>,
    pub commit_count: u64,
    pub streak: u64,
}

impl Pet {
    pub fn new(name: String, species: String) -> Self {
        Pet {
            name,
            species,
            stage: "Egg".to_string(),
            xp: 0,
            hunger: 0,
            last_commit_date: None,
            commit_count: 0,
            streak: 0,
        }
    }

    pub fn calculate_mood(&self) -> String {
        let days_inactive = match self.last_commit_date {
            Some(last) => {
                let today = chrono::Utc::now().date_naive();
                (today - last).num_days()
            }
            None => i64::MAX,
        };

        if self.hunger > 80 {
            "sick".to_string()
        } else if days_inactive > 7 {
            "sick".to_string()
        } else if days_inactive > 2 {
            "sad".to_string()
        } else if self.hunger > 50 {
            "sad".to_string()
        } else {
            "happy".to_string()
        }
    }

    pub fn current_stage(&self) -> String {
        self.stage.clone()
    }

    pub fn xp_for_next_level(&self) -> u64 {
        match self.stage.as_str() {
            "Egg" => 100,
            "Baby" => 300,
            "Child" => 600,
            "Adult" => 1000,
            "Elder" => u64::MAX,
            _ => 100,
        }
    }

    pub fn maybe_evolve(&mut self) {
        let next_threshold = self.xp_for_next_level();
        if self.xp >= next_threshold {
            let next_stage = match self.stage.as_str() {
                "Egg" => "Baby",
                "Baby" => "Child",
                "Child" => "Adult",
                "Adult" => "Elder",
                _ => return,
            };
            self.stage = next_stage.to_string();
            println!("🎉 Your pet evolved to {}!", next_stage);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::{NaiveDate, Duration};

    #[test]
    fn test_new_pet() {
        let pet = Pet::new("Test".to_string(), "Cat".to_string());
        assert_eq!(pet.name, "Test");
        assert_eq!(pet.species, "Cat");
        assert_eq!(pet.stage, "Egg");
        assert_eq!(pet.xp, 0);
        assert_eq!(pet.hunger, 0);
        assert!(pet.last_commit_date.is_none());
        assert_eq!(pet.commit_count, 0);
        assert_eq!(pet.streak, 0);
    }

    #[test]
    fn test_mood_happy() {
        let mut pet = Pet::new("Test".to_string(), "Cat".to_string());
        let today = chrono::Utc::now().date_naive();
        pet.last_commit_date = Some(today - Duration::days(1));
        pet.hunger = 10;
        assert_eq!(pet.calculate_mood(), "happy");
    }

    #[test]
    fn test_mood_sad_due_to_inactivity() {
        let mut pet = Pet::new("Test".to_string(), "Cat".to_string());
        let today = chrono::Utc::now().date_naive();
        pet.last_commit_date = Some(today - Duration::days(5));
        pet.hunger = 10;
        assert_eq!(pet.calculate_mood(), "sad");
    }

    #[test]
    fn test_mood_sick_due_to_starvation() {
        let mut pet = Pet::new("Test".to_string(), "Cat".to_string());
        let today = chrono::Utc::now().date_naive();
        pet.last_commit_date = Some(today - Duration::days(1));
        pet.hunger = 90;
        assert_eq!(pet.calculate_mood(), "sick");
    }

    #[test]
    fn test_xp_for_level() {
        let mut pet = Pet::new("Test".to_string(), "Cat".to_string());
        assert_eq!(pet.xp_for_next_level(), 100);
        pet.stage = "Baby".to_string();
        assert_eq!(pet.xp_for_next_level(), 300);
        pet.stage = "Child".to_string();
        assert_eq!(pet.xp_for_next_level(), 600);
        pet.stage = "Adult".to_string();
        assert_eq!(pet.xp_for_next_level(), 1000);
        pet.stage = "Elder".to_string();
        assert_eq!(pet.xp_for_next_level(), u64::MAX);
    }

    #[test]
    fn test_evolution() {
        let mut pet = Pet::new("Test".to_string(), "Cat".to_string());
        assert_eq!(pet.stage, "Egg");
        pet.xp = 100;
        pet.maybe_evolve();
        assert_eq!(pet.stage, "Baby");
        pet.xp = 300;
        pet.maybe_evolve();
        assert_eq!(pet.stage, "Child");
        pet.xp = 600;
        pet.maybe_evolve();
        assert_eq!(pet.stage, "Adult");
        pet.xp = 1000;
        pet.maybe_evolve();
        assert_eq!(pet.stage, "Elder");
        pet.xp = 2000;
        pet.maybe_evolve();
        assert_eq!(pet.stage, "Elder");
    }
}