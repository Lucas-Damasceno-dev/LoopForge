package repository

import (
	"database/sql"
	"errors"
	"time"

	"booking-system/internal/models"
)

var (
	ErrEmailExists = errors.New("e-mail já cadastrado")
	ErrNotFound    = errors.New("registro não encontrado")
)

type UserRepository struct {
	db *sql.DB
}

func NewUserRepository(db *sql.DB) *UserRepository { return &UserRepository{db: db} }

func (r *UserRepository) Create(u *models.User) error {
	now := time.Now()
	u.CreatedAt, u.UpdatedAt = now, now
	_, err := r.db.Exec(
		"INSERT INTO users (name, email, password_hash, role, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
		u.Name, u.Email, u.PasswordHash, u.Role, now, now,
	)
	if err != nil && isUniqueViolation(err) {
		return ErrEmailExists
	}
	return err
}

func (r *UserRepository) GetByEmail(email string) (*models.User, error) {
	u := &models.User{}
	err := r.db.QueryRow(`SELECT id, name, email, password_hash, role, created_at, updated_at FROM users WHERE email = ?`, email).
		Scan(&u.ID, &u.Name, &u.Email, &u.PasswordHash, &u.Role, &u.CreatedAt, &u.UpdatedAt)
	if err == sql.ErrNoRows {
		return nil, ErrNotFound
	}
	return u, err
}

func (r *UserRepository) GetByID(id int64) (*models.User, error) {
	u := &models.User{}
	err := r.db.QueryRow(`SELECT id, name, email, password_hash, role, created_at, updated_at FROM users WHERE id = ?`, id).
		Scan(&u.ID, &u.Name, &u.Email, &u.PasswordHash, &u.Role, &u.CreatedAt, &u.UpdatedAt)
	if err == sql.ErrNoRows {
		return nil, ErrNotFound
	}
	return u, err
}

func isUniqueViolation(err error) bool {
	// SQLite unique constraint error string e.g. "UNIQUE constraint failed: users.email"
	return errors.Is(err, sqlite3.ErrConstraintUnique)
}