package main

import (
	"fmt"
	"net/http"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

var (
	pingSuccess = prometheus.NewCounter(
		prometheus.CounterOpts{
			Name: "ping_success_total",
			Help: "Total number of successful pings",
		},
	)
	pingFailure = prometheus.NewCounter(
		prometheus.CounterOpts{
			Name: "ping_failure_total",
			Help: "Total number of failed pings",
		},
	)
	pingLatency = prometheus.NewHistogram(
		prometheus.HistogramOpts{
			Name: "ping_latency_seconds",
			Help: "Latency of HTTP pings in seconds",
			Buckets: prometheus.DefBuckets,
		},
	)
)

func init() {
	prometheus.MustRegister(pingSuccess, pingFailure, pingLatency)
}

func main() {
	target := "https://google.com"

	client := &http.Client{
		Timeout: 10 * time.Second,
	}

	go func() {
		for {
			start := time.Now()
			resp, err := client.Get(target)
			latency := time.Since(start)

			if err != nil {
				pingFailure.Inc()
				fmt.Printf("[DOWN] %s - error: %v\n", target, err)
			} else {
				pingSuccess.Inc()
				pingLatency.Observe(latency.Seconds())
				fmt.Printf("[UP] %s - status: %d, latency: %v\n", target, resp.StatusCode, latency.Truncate(time.Millisecond))
				resp.Body.Close()
			}

			time.Sleep(30 * time.Second)
		}
	}()

	http.Handle("/metrics", promhttp.Handler())
	fmt.Println("Prometheus metrics available on :8080/metrics")
	http.ListenAndServe(":8080", nil)
}
