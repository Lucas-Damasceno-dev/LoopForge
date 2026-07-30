use anyhow::{Context, Result};
use std::fs;
use std::path::PathBuf;

pub fn execute() -> Result<()> {
    let home = dirs::home_dir().context("Cannot determine home directory")?;
    let hook_dir = home.join(".config/git/hooks");
    fs::create_dir_all(&hook_dir).context("Failed to create hooks directory")?;

    let hook_script = r#"#!/bin/sh
# post-commit hook for git-pet
git-pet commit-event
"#;

    let hook_path = hook_dir.join("post-commit");
    fs::write(&hook_path, hook_script).context("Failed to write post-commit hook")?;

    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let mut perms = fs::metadata(&hook_path)?.permissions();
        perms.set_mode(0o755);
        fs::set_permissions(&hook_path, perms)?;
    }

    println!("Git hook installed at {}", hook_path.display());
    println!("Make sure Git is configured: git config --global core.hooksPath '{}'", hook_dir.display());
    Ok(())
}