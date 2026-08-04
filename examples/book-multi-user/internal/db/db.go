package db

import (
	"database/sql"
	"embed"
	"fmt"
	"log"
	"os"

	_ "modernc.org/sqlite"
)

//go:embed migrations/*.sql
var migrationsFS embed.FS

func Open(path string) (*sql.DB, error) {
	dsn := fmt.Sprintf("file:%s?_pragma=foreign_keys(1)&_pragma=journal_mode(WAL)", path)
	return sql.Open("sqlite", dsn)
}

func Migrate(db *sql.DB) error {
	entries, err := migrationsFS.ReadDir("migrations")
	if err != nil {
		return err
	}
	for _, e := range entries {
		content, _ := migrationsFS.ReadFile("migrations/" + e.Name())
		if _, err := db.Exec(string(content)); err != nil {
			return fmt.Errorf("migration %s failed: %w", e.Name(), err)
		}
		log.Printf("migration %s applied", e.Name())
	}
	return nil
}

func Seed(db *sql.DB) error {
	// verificar se já há admin
	var count int
	if err := db.QueryRow("SELECT COUNT(*) FROM users").Scan(&count); err != nil {
		return err
	}
	if count > 0 {
		return nil
	}

	// inserts...
	// (simplificado: use exec para inserir admin, dois profissionais e serviços)
	// hashs com bcrypt
	hashAdmin, _ := bcrypt.GenerateFromPassword([]byte("admin123"), 10)
	_, err := db.Exec("INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
		"Administrador", "admin@example.com", string(hashAdmin), "admin")
	if err != nil {
		return err
	}
	hashProf1, _ := bcrypt.GenerateFromPassword([]byte("password1"), 10)
	_, err = db.Exec("INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
		"Dr. Almeida", "almeida@example.com", string(hashProf1), "professional")
	// ...
	return nil
}