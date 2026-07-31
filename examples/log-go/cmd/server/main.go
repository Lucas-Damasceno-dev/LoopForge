package main

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/example/logingestor/internal/adapters/http"
	"github.com/example/logingestor/internal/config"
	"github.com/example/logingestor/internal/domain"
	"github.com/example/logingestor/internal/metrics"
	"github.com/example/logingestor/internal/repository/memory"
	"github.com/example/logingestor/internal/repository/postgres"
	"github.com/example/logingestor/internal/usecase"
)

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	if err := run(logger); err != nil {
		logger.Error("server failed", "error", err)
		os.Exit(1)
	}
}

// run inicializa configuração, dependências e o servidor HTTP com graceful shutdown.
func run(logger *slog.Logger) error {
	cfg, err := config.Load()
	if err != nil {
		return fmt.Errorf("load config: %w", err)
	}

	var repo domain.LogRepository
	if cfg.DatabaseURL != "" {
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()

		pgRepo, err := postgres.New(ctx, cfg.DatabaseURL)
		if err != nil {
			return fmt.Errorf("connect to postgres: %w", err)
		}
		repo = pgRepo
	} else {
		logger.Warn("DATABASE_URL not set; using in-memory log repository")
		repo = memory.New()
	}

	defer func() {
		if err := repo.Close(); err != nil {
			logger.Error("failed to close repository", "error", err)
		}
	}()

	defaultSeverity, err := domain.ParseSeverity(cfg.MinSeverity)
	if err != nil {
		return fmt.Errorf("invalid min severity: %w", err)
	}

	classifier := usecase.NewConfigurableClassifier(usecase.ClassifierConfig{
		DefaultSeverity: defaultSeverity,
		ErrorKeywords:   cfg.ErrorKeywords,
		WarnKeywords:    cfg.WarnKeywords,
	})

	ingestor := usecase.NewIngestLogUseCase(repo, classifier, defaultSeverity)

	metricCollector, err := metrics.New()
	if err != nil {
		return fmt.Errorf("init metrics: %w", err)
	}

	handler, err := http.NewHandler(ingestor, metricCollector, logger)
	if err != nil {
		return fmt.Errorf("init http handler: %w", err)
	}

	router := http.NewRouter(handler, metricCollector, cfg.APIKey)

	server := &http.Server{
		Addr:         fmt.Sprintf(":%d", cfg.Port),
		Handler:      router,
		ReadTimeout:  cfg.ReadTimeout,
		WriteTimeout: cfg.WriteTimeout,
		IdleTimeout:  60 * time.Second,
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	errCh := make(chan error, 1)
	go func() {
		errCh <- server.ListenAndServe()
	}()

	select {
	case err := <-errCh:
		if err != nil && !errors.Is(err, http.ErrServerClosed) {
			return fmt.Errorf("http server: %w", err)
		}
		return nil
	case <-ctx.Done():
		shutdownCtx, cancel := context.WithTimeout(context.Background(), cfg.ShutdownTimeout)
		defer cancel()
		if err := server.Shutdown(shutdownCtx); err != nil {
			return fmt.Errorf("shutdown server: %w", err)
		}
		return nil
	}
}