package main

import (
	"log"
	"net/http"
	"os"

	"booking-system/internal/api"
	"booking-system/internal/config"
	"booking-system/internal/db"
	_ "modernc.org/sqlite"
)

func main() {
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("config: %v", err)
	}
	database, err := db.Open(cfg.DatabasePath)
	if err != nil {
		log.Fatalf("db open: %v", err)
	}
	defer database.Close()
	if err := db.Migrate(database); err != nil {
		log.Fatalf("migrate: %v", err)
	}
	if err := db.Seed(database); err != nil {
		log.Fatalf("seed: %v", err)
	}
	srv := api.NewServer(database, cfg)
	addr := os.Getenv("ADDR")
	if addr == "" {
		addr = ":8080"
	}
	log.Printf("listening on %s", addr)
	if err := http.ListenAndServe(addr, srv.Router()); err != nil {
		log.Fatal(err)
	}
}