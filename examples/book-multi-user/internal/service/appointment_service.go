package service

import (
	"errors"
	"time"

	"booking-system/internal/models"
	"booking-system/internal/repository"
)

var (
	ErrOverlap           = errors.New("Horário ocupado")
	ErrPast              = errors.New("Não é possível agendar no passado")
	ErrOutsideWorking    = errors.New("Fora do horário de trabalho")
	ErrMissingReason     = errors.New("Motivo é obrigatório")
	ErrCannotCancelPast  = errors.New("Não é possível cancelar agendamento passado")
	ErrNotAuthorized     = errors.New("Não autorizado")
	ErrServiceNotFound   = errors.New("Serviço não encontrado")
	ErrAppointmentNotFound = errors.New("Agendamento não encontrado")
)

type AppointmentService struct {
	appointmentRepo *repository.AppointmentRepository
	serviceRepo     *repository.ServiceRepository
	professionalRepo *repository.ProfessionalRepository
	clientRepo      *repository.UserRepository
}

func NewAppointmentService(...)*AppointmentService { ... }

func (s *AppointmentService) CreateAppointment(clientID, serviceID int64, start time.Time) (*models.Appointment, error) {
	service, err := s.serviceRepo.GetByID(serviceID)
	if err != nil {
		return nil, ErrServiceNotFound
	}
	// check past (minute tolerance)
	if start.Before(time.Now().Truncate(time.Minute)) {
		return nil, ErrPast
	}
	// working hours 08:00–18:00 Mon–Fri
	if start.Weekday() == time.Sunday || start.Weekday() == time.Saturday ||
		start.Hour() < 8 || start.Hour() >= 18 {
		return nil, ErrOutsideWorking
	}
	// check end time within same day
	end := start.Add(time.Duration(service.DurationMinutes) * time.Minute)
	if end.Hour() < 8 || end.Hour() > 18 || end.Day() != start.Day() {
		return nil, ErrOutsideWorking
	}
	// conflict detection
	hasConflict, err := s.appointmentRepo.ExistsOverlap(service.ProfessionalID, start, end)
	if err != nil {
		return nil, err
	}
	if hasConflict {
		return nil, ErrOverlap
	}
	appt := &models.Appointment{
		ClientID:       clientID,
		ProfessionalID: service.ProfessionalID,
		ServiceID:      serviceID,
		StartTime:      start,
		EndTime:        end,
		Status:         models.StatusScheduled,
	}
	if err := s.appointmentRepo.Create(appt); err != nil {
		return nil, err
	}
	// create notifications
	_ = s.appointmentRepo.CreateNotification(appt.ClientID, "Agendamento confirmado")
	_ = s.appointmentRepo.CreateNotification(appt.ProfessionalID, "Novo agendamento criado")
	return appt, nil
}

func (s *AppointmentService) CancelAppointment(appointmentID int64, reason string, actorID int64, actorRole string) error {
	if strings.TrimSpace(reason) == "" {
		return ErrMissingReason
	}
	appt, err := s.appointmentRepo.GetByID(appointmentID)
	if err != nil {
		return ErrAppointmentNotFound
	}
	if appt.StartTime.Before(time.Now()) {
		return ErrCannotCancelPast
	}
	if actorRole == "client" && appt.ClientID != actorID {
		return ErrNotAuthorized
	}
	appt.Status = models.StatusCancelled
	appt.CancellationReason = reason
	if err := s.appointmentRepo.Update(appt); err != nil {
		return err
	}
	// notify both
	_ = s.appointmentRepo.CreateNotification(appt.ClientID, "Seu agendamento foi cancelado")
	_ = s.appointmentRepo.CreateNotification(appt.ProfessionalID, "Agendamento cancelado")
	return nil
}