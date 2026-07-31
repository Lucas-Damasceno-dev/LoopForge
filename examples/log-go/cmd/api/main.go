// Command api executa o microserviço de ingestão de logs.
package main

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"

	"github.com/example/log-ingestor/internal/config"
	"github.com/example/log-ingestor/internal/domain"
	httpapi "github.com/example/log-ingestor/internal/interface/http"
	"github.com/example/log-ingestor/internal/infrastructure/metrics"
	"github.com/example/log-ingestor/internal/infrastructure/persistence"
	"github.com/example/log-ingestor/internal/usecase"
)

func main() {
	if err := run(); err != nil {
		slog.Error("fatal error", "error", err)
		os.Exit(1)
	}
}

func run() error {
	cfg, err := config.Load()
	if err != nil {
		return fmt.Errorf("load config: %w", err)
	}

	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	slog.SetDefault(logger)

	var repo domain.LogRepository
	if cfg.DBDriver == "postgres" {
		repo, err = persistence.NewPostgresRepository(cfg.DatabaseURL)
		if err != nil {
			return fmt.Errorf("init postgres repository: %w", err)
		}
	} else {
		repo = persistence.NewMemoryRepository()
		slog.Warn("using in-memory repository; logs will not persist")
	}
	defer func() {
		if err := repo.Close(); err != nil {
			slog.Error("failed to close repository", "error", err)
		}
	}()

	m, err := metrics.New()
	if err != nil {
		return fmt.Errorf("init metrics: %w", err)
	}

	processor, err := usecase.NewProcessor(repo, m, cfg.LogMinLevel, cfg.SeverityRules)
	if err != nil {
		return fmt.Errorf("init log processor: %w", err)
	}

	handler, err := httpapi.NewHandler(processor, m, cfg.MaxBodyBytes)
	if err != nil {
		return fmt.Errorf("init http handler: %w", err)
	}

	server := &http.Server{
		Addr:         ":" + strings.TrimPrefix(cfg.HTTPPort, ":"),
		Handler:      handler.Routes(m.Handler(), cfg.APIKey),
		ReadTimeout:  cfg.ReadTimeout,
		WriteTimeout: cfg.WriteTimeout,
		IdleTimeout:  cfg.IdleTimeout,
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	errCh := make(chan error, 1)
	go func() {
		logger.Info("http server started", "addr", server.Addr)
		if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			errCh <- err
		}
	}()

	select {
	case err := <-errCh:
		return fmt.Errorf("http server error: %w", err)
	case <-ctx.Done():
		logger.Info("shutdown signal received")
		shutdownCtx, cancel := context.WithTimeout(context.Background(), cfg.ShutdownTimeout)
		defer cancel()
		if err := server.Shutdown(shutdownCtx); err != nil {
			return fmt.Errorf("graceful shutdown failed: %w", err)
		}
		return nil
	}
}