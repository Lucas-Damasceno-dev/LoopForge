use crate::pet::{EvolutionStage, Pet};

pub fn render(pet: &Pet) -> String {
    let mood = pet.mood();
    let stage = &pet.evolution_stage;
    let art = match stage {
        EvolutionStage::Egg => match mood {
            "happy" => " (o.o) ",
            "neutral" => " (._.) ",
            "sad" => " (;.;) ",
            "sick" => " (x.x) ",
            _ => " (._.) ",
        },
        EvolutionStage::Baby => match mood {
            "happy" => r#" 
  \(\`v\`\) 
  ( >_< )
 "#,
            "neutral" => r#" 
  (o.o)
  (   )
 "#,
            "sad" => r#" 
  (;_;)
  (   )
 "#,
            "sick" => r#" 
  (x.x)
  (   )
 "#,
            _ => r#" 
  (o.o)
  (   )
 "#,
        },
        EvolutionStage::Teen => match mood {
            "happy" => r#" 
   /ᐠ｡‸｡ᐟ\
   ( >_<)
 "#,
            "neutral" => r#" 
   /ᐠ｡‸｡ᐟ\
   ( o.o )
 "#,
            "sad" => r#" 
   /ᐠ｡‸｡ᐟ\
   ( ;_; )
 "#,
            "sick" => r#" 
   /ᐠ｡‸｡ᐟ\
   ( x.x )
 "#,
            _ => r#" 
   /ᐠ｡‸｡ᐟ\
   ( o.o )
 "#,
        },
        EvolutionStage::Adult => match mood {
            "happy" => r#" 
   /\_/\
  ( ᵒ ᵒ )
  ( >_<)
 "#,
            "neutral" => r#" 
   /\_/\
  ( o o )
  (   )
 "#,
            "sad" => r#" 
   /\_/\
  ( ; ; )
  (   )
 "#,
            "sick" => r#" 
   /\_/\
  ( x x )
  (   )
 "#,
            _ => r#" 
   /\_/\
  ( o o )
  (   )
 "#,
        },
        EvolutionStage::Legendary => match mood {
            "happy" => r#" 
   ╱▔▔╲
  ( ᵒ ᵒ )
  ( >_<)
   ╲▁▁╱
 "#,
            "neutral" => r#" 
   ╱▔▔╲
  ( o o )
  (   )
   ╲▁▁╱
 "#,
            "sad" => r#" 
   ╱▔▔╲
  ( ; ; )
  (   )
   ╲▁▁╱
 "#,
            "sick" => r#" 
   ╱▔▔╲
  ( x x )
  (   )
   ╲▁▁╱
 "#,
            _ => r#" 
   ╱▔▔╲
  ( o o )
  (   )
   ╲▁▁╱
 "#,
        },
    };

    format!(
        "\n{}\n  Name: {}  |  Stage: {:?}  |  Mood: {}  |  HP: {}  |  Hunger: {}  |  Level: {}  |  XP: {}/{}\n",
        art,
        pet.name,
        pet.evolution_stage,
        mood,
        pet.calculate_happiness(),
        pet.hunger,
        pet.level,
        pet.xp,
        pet.xp_for_next_level()
    )
}