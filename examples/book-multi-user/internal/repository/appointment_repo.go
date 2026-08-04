package repository

import (
	"database/sql"
	"time"

	"booking-system/internal/models"
)

type AppointmentRepository struct{ db *sql.DB }

func (r *AppointmentRepository) Create(a *models.Appointment) error {
	now := time.Now()
	a.CreatedAt, a.UpdatedAt = now, now
	_, err := r.db.Exec(`
		INSERT INTO appointments (client_id, professional_id, service_id, start_time, end_time, status, cancellation_reason, created_at, updated_at)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		a.ClientID, a.ProfessionalID, a.ServiceID, a.StartTime, a.EndTime, a.Status, a.CancellationReason, now, now)
	return err
}

func (r *AppointmentRepository) ExistsOverlap(professionalID int64, start, end time.Time) (bool, error) {
	var exists bool
	err := r.db.QueryRow(`
		SELECT EXISTS(
			SELECT 1 FROM appointments
			WHERE professional_id = ? AND status != 'cancelled' AND start_time < ? AND end_time > ?
		)`, professionalID, end, start).Scan(&exists)
	return exists, err
}

func (r *AppointmentRepository) GetByID(id int64) (*models.Appointment, error) { ... }
func (r *AppointmentRepository) Update(a *models.Appointment) error { ... }

func (r *AppointmentRepository) CreateNotification(userID int64, msg string) error {
	_, err := r.db.Exec("INSERT INTO notifications (user_id, message) VALUES (?, ?)", userID, msg)
	return err
}