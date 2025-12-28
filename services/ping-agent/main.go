package main

import (
	"fmt"
	"net/http"
	"os"
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
	targetsEnv := os.Getenv("PING_TARGET_URLS")
	if targetsEnv == "" {
		targetsEnv = "https://google.com"
	}
	var targets []string
	for _, raw := range strings.Split(targetsEnv, ",") {
		target := strings.TrimSpace(raw)
		if target != "" {
			targets = append(targets, target)
		}
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
