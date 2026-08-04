package service

import (
	"errors"
	"regexp"
	"strings"

	"booking-system/internal/models"
	"booking-system/internal/repository"
	"golang.org/x/crypto/bcrypt"
)

var (
	ErrInvalidData      = errors.New("dados inválidos")
	ErrEmailTaken       = errors.New("e-mail já cadastrado")
	ErrRoleNotAllowed   = errors.New("papel não permitido")
)

type UserInput struct {
	Name     string
	Email    string
	Password string
	Role     string
}

type UserService struct {
	repo *repository.UserRepository
}

func NewUserService(r *repository.UserRepository) *UserService { return &UserService{repo: r} }

func (s *UserService) CreateUser(in UserInput) (*models.User, error) {
	if strings.TrimSpace(in.Name) == "" || strings.TrimSpace(in.Email) == "" || in.Password == "" {
		return nil, ErrInvalidData
	}
	if in.Role != "client" && in.Role != "professional" {
		return nil, ErrRoleNotAllowed
	}
	if !validEmail(in.Email) {
		return nil, ErrInvalidData
	}
	hash, err := bcrypt.GenerateFromPassword([]byte(in.Password), bcrypt.DefaultCost)
	if err != nil {
		return nil, err
	}
	u := &models.User{
		Name:         strings.TrimSpace(in.Name),
		Email:        strings.ToLower(strings.TrimSpace(in.Email)),
		PasswordHash: string(hash),
		Role:         in.Role,
	}
	if err := s.repo.Create(u); err != nil {
		if err == repository.ErrEmailExists {
			return nil, ErrEmailTaken
		}
		return nil, err
	}
	return u, nil
}

func (s *UserService) GetAvailableRoles() []string {
	return []string{"client", "professional"}
}

func validEmail(email string) bool {
	re := regexp.MustCompile(`^[^@]+@[^@]+\.[^@]+$`)
	return re.MatchString(email)
}