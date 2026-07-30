use std::env;
use tempfile::TempDir;

fn setup_test_env() -> TempDir {
    let tmp = TempDir::new().unwrap();
    let data_home = tmp.path().join("data");
    std::fs::create_dir_all(&data_home).unwrap();
    env::set_var("XDG_DATA_HOME", data_home);
    tmp
}

#[test]
fn test_full_flow() {
    let _tmp = setup_test_env();

    // No pet initially
    assert!(git_pet::commands::status::execute().is_err());

    // Create pet
    git_pet::commands::init::execute("Fluffy".to_string()).unwrap();
    assert!(git_pet::commands::status::execute().is_ok());
    assert!(git_pet::commands::stats::execute().is_ok());
    assert!(git_pet::commands::feed::execute().is_ok());

    // Simulate a commit
    assert!(git_pet::commands::commit_event::execute().is_ok());

    let state = git_pet::state::load_state().unwrap().unwrap();
    assert_eq!(state.pet.streak, 1);
    assert_eq!(state.pet.commit_count, 1);
    assert!(state.pet.xp >= 10);
}

#[test]
fn test_multiple_commits_same_day() {
    let _tmp = setup_test_env();
    git_pet::commands::init::execute("Streaky".to_string()).unwrap();

    git_pet::commands::commit_event::execute().unwrap();
    let state = git_pet::state::load_state().unwrap().unwrap();
    assert_eq!(state.pet.streak, 1);

    // Second commit same day → streak should stay 1
    git_pet::commands::commit_event::execute().unwrap();
    let state = git_pet::state::load_state().unwrap().unwrap();
    assert_eq!(state.pet.streak, 1);
}