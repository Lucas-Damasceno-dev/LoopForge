use crate::state::PetState;

/// Returns the appropriate ASCII art for the pet's current stage and mood.
fn get_art(state: &PetState) -> String {
    let is_sad = state.happiness < 30;

    match state.stage.as_str() {
        "Master" if is_sad => "   /\\_/\\_/\\\\n  (  x_x  )\n   >  -  <\n  /  | |  \\".to_string(),
        "Master" => "   /\\_/\\_/\\\\n  (  ^_^  )\n   >  -  <\n  /  | |  \\".to_string(),
        "Adult" if is_sad => "    /\\___/\\\n   (  x x  )\n   /  >x<  \\\n  /        \\".to_string(),
        "Adult" => "    /\\___/\\\n   (  o o  )\n   /  >_<  \\\n  /        \\".to_string(),
        "Teen" if is_sad => "   ╲╱ ╲╱\n  (  x_x)\n  /  |  \\\n     |\n    / \\".to_string(),
        "Teen" => "   ╲╱ ╲╱\n  ( •_•)\n  /  |  \\\n     |\n    / \\".to_string(),
        "Baby" if is_sad => "    ╲╱\n   (x_x)\n   / ε \\\n   \\   /".to_string(),
        "Baby" => "    ╲╱\n   (•_•)\n   / ε \\\n   \\   /".to_string(),
        _ if is_sad => "   _________\n  /         \\\n  |  (x_x)  |\n  |   <)|   |\n  \\_________/".to_string(),
        _ => "   _________\n  /         \\\n  |  (•_•)  |\n  |   <)|   |\n  \\_________/".to_string(),
    }
}

/// Returns a mood label based on happiness level.
fn get_mood_label(state: &PetState) -> &'static str {
    if state.happiness > 70 {
        "Happy"
    } else if state.happiness > 30 {
        "Neutral"
    } else {
        "Sad / Sick"
    }
}

/// Renders the full status output with colored ASCII art and pet info.
pub fn render(state: &PetState) -> String {
    use crossterm::style::Stylize;

    let art = get_art(state);
    let mood = get_mood_label(state);

    // Choose color based on happiness
    let colored_art = if state.happiness > 70 {
        art.green()
    } else if state.happiness > 30 {
        art.yellow()
    } else {
        art.red()
    };

    format!(
        "{}\n\n{} the {} ({})\nHP: {} | Hunger: {} | XP: {} | Stage: {} | Streak: {} days\n",
        colored_art,
        state.name,
        state.species,
        mood,
        state.happiness,
        state.hunger,
        state.xp,
        state.stage,
        state.current_streak,
    )
}