package config

import (
	"fmt"
	"os"
	"time"
)

type Config struct {
	DatabasePath string
	JWTSecret    string
	TokenExpiry  time.Duration
	DBDSN        string
}

func Load() (*Config, error) {
	cfg := &Config{
		DatabasePath: os.Getenv("DB_PATH"),
		JWTSecret:    os.Getenv("JWT_SECRET"),
		TokenExpiry:  24 * time.Hour, // default
	}
	if cfg.DatabasePath == "" {
		cfg.DatabasePath = "booking.db"
	}
	if cfg.JWTSecret == "" {
		return nil, fmt.Errorf("JWT_SECRET is required")
	}
	if v := os.Getenv("JWT_EXPIRY_HOURS"); v != "" {
		hours, err := strconv.Atoi(v)
		if err != nil {
			return nil, fmt.Errorf("JWT_EXPIRY_HOURS must be integer")
		}
		cfg.TokenExpiry = time.Duration(hours) * time.Hour
	}
	cfg.DatabaseDSN = fmt.Sprintf("file:%s?_pragma=busy_timeout(5000)&_pragma=journal_mode(WAL)", cfg.DatabasePath)
	return cfg, nil
}