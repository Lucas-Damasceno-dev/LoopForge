package httpapi

import (
	"encoding/json"
	"log"
	"net/http"
)

func writeJSON(w http.ResponseWriter, status int, payload interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(payload); err != nil {
		log.Printf("failed to encode response: %v", err)
	}
}

func writeError(w http.ResponseWriter, status int, message string, err error) {
	body := map[string]string{
		"error":   http.StatusText(status),
		"message": message,
	}

	if err != nil && status < http.StatusInternalServerError {
		body["detail"] = err.Error()
	}

	writeJSON(w, status, body)
}