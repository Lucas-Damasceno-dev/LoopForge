package api

import (
	"context"
	"encoding/json"
	"net/http"

	"booking-system/internal/config"
	"booking-system/internal/repository"
	"booking-system/internal/service"
	"github.com/golang-jwt/jwt/v5"
)

type Server struct {
	cfg        *config.Config
	db         *sql.DB
	userSvc    *service.UserService
	apptSvc    *service.AppointmentService
	userRepo   *repository.UserRepository
}

func NewServer(db *sql.DB, cfg *config.Config) *Server {
	// initialize repos and services
	return &Server{...}
}

func (s *Server) Router() http.Handler {
	mux := http.NewServeMux()
	// public routes
	mux.HandleFunc("/api/auth/login", s.handleLogin)
	mux.HandleFunc("/api/auth/register", s.handleRegister)
	// protected
	mux.Handle("/api/professionals", s.authMiddleware(http.HandlerFunc(s.listProfessionals)))
	mux.Handle("/api/appointments", s.authMiddleware(http.HandlerFunc(s.createAppointment)))
	mux.Handle("/api/appointments/{id}/cancel", s.authMiddleware(http.HandlerFunc(s.cancelAppointment)))
	// admin only
	mux.Handle("/api/admin/appointments", s.authMiddleware(s.requireRole("admin", http.HandlerFunc(s.adminListAppointments))))
	return mux
}

// Handlers with JSON responses...