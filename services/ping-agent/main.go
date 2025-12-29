package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

var (
	pingSuccess = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "ping_success_total",
			Help: "Total number of successful pings",
		},
		[]string{"target"},
	)
	pingFailure = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "ping_failure_total",
			Help: "Total number of failed pings",
		},
		[]string{"target"},
	)
	pingLatency = prometheus.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "ping_latency_seconds",
			Help:    "Latency of HTTP pings in seconds",
			Buckets: prometheus.DefBuckets,
		},
		[]string{"target"},
	)
)

func init() {
	prometheus.MustRegister(pingSuccess, pingFailure, pingLatency)
}

func main() {
	var targets []string
	targets, err := loadTargets("/config/targets.json")
	if err != nil || len(targets) == 0 {
		targets = parseTargetsEnv(os.Getenv("PING_TARGET_URLS"))
	}
	if len(targets) == 0 {
		targets = []string{"https://google.com"}
	}

	client := &http.Client{
		Timeout: 10 * time.Second,
	}

	go func() {
		for {
			for _, target := range targets {
				start := time.Now()
				resp, err := client.Get(target)
				latency := time.Since(start)

				if err != nil {
					pingFailure.WithLabelValues(target).Inc()
					fmt.Printf("[DOWN] %s - error: %v\n", target, err)
				} else {
					pingSuccess.WithLabelValues(target).Inc()
					pingLatency.WithLabelValues(target).Observe(latency.Seconds())
					fmt.Printf("[UP] %s - status: %d, latency: %v\n", target, resp.StatusCode, latency.Truncate(time.Millisecond))
					resp.Body.Close()
				}
			}

			time.Sleep(30 * time.Second)
		}
	}()

	http.Handle("/metrics", promhttp.Handler())
	http.HandleFunc("/healthz", func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("ok"))
	})
	fmt.Println("Prometheus metrics available on :8080/metrics")
	http.ListenAndServe(":8080", nil)
}

func loadTargets(path string) ([]string, error) {
	data, err := os.ReadFile(filepath.Clean(path))
	if err != nil {
		return nil, err
	}
	var raw []string
	if err := json.Unmarshal(data, &raw); err != nil {
		return nil, err
	}
	var targets []string
	for _, target := range raw {
		target = strings.TrimSpace(target)
		if target != "" {
			targets = append(targets, target)
		}
	}
	return targets, nil
}

func parseTargetsEnv(value string) []string {
	if value == "" {
		return nil
	}
	var targets []string
	for _, raw := range strings.Split(value, ",") {
		target := strings.TrimSpace(raw)
		if target != "" {
			targets = append(targets, target)
		}
	}
	return targets
}
