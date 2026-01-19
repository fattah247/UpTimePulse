package main

import (
	"context"
	"errors"
	"io"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"sync"
	"syscall"
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
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	client := &http.Client{
		Timeout: 10 * time.Second,
	}
	pingInterval := getenvDurationSeconds("PING_INTERVAL_SECONDS", 30)
	concurrency := getenvInt("PING_CONCURRENCY", 5)
	maxBodyBytes := int64(getenvInt("PING_BODY_MAX_BYTES", 65536))
	httpMethod := strings.ToUpper(getenvOrDefault("PING_HTTP_METHOD", "GET"))
	useRange := getenvBool("PING_RANGE_REQUEST", true)

	go func() {
		pingTicker := time.NewTicker(pingInterval)
		defer pingTicker.Stop()

		targets := loadTargetsFromEnv()
		if len(targets) == 0 {
			targets = defaultTargets()
		}
		runCycle := func() {
			cycleCtx, cancel := context.WithTimeout(ctx, pingInterval)
			defer cancel()
			pingTargets(cycleCtx, client, targets, concurrency, maxBodyBytes, httpMethod, useRange)
		}
		runCycle()
		for {
			select {
			case <-ctx.Done():
				return
			case <-pingTicker.C:
				runCycle()
			}
		}
	}()

	mux := http.NewServeMux()
	mux.Handle("/metrics", promhttp.Handler())
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("ok"))
	})
	server := &http.Server{
		Addr:    ":8080",
		Handler: mux,
	}
	serverErrCh := make(chan error, 1)
	go func() {
		serverErrCh <- server.ListenAndServe()
	}()
	log.Println("Prometheus metrics available on :8080/metrics")

	var serverErr error
	select {
	case <-ctx.Done():
	case err := <-serverErrCh:
		serverErr = err
	}

	shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := server.Shutdown(shutdownCtx); err != nil {
		log.Printf("HTTP server shutdown error: %v", err)
	}

	if serverErr == nil {
		serverErr = <-serverErrCh
	}
	if serverErr != nil && !errors.Is(serverErr, http.ErrServerClosed) {
		log.Fatalf("HTTP server error: %v", serverErr)
	}
}

func pingTargets(ctx context.Context, client *http.Client, targets []string, concurrency int, maxBodyBytes int64, httpMethod string, useRange bool) {
	if len(targets) == 0 {
		return
	}
	if concurrency < 1 {
		concurrency = 1
	}
	if concurrency > len(targets) {
		concurrency = len(targets)
	}

	jobs := make(chan string)
	var wg sync.WaitGroup
	for i := 0; i < concurrency; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for target := range jobs {
				if ctx.Err() != nil {
					return
				}
				pingTarget(ctx, client, target, maxBodyBytes, httpMethod, useRange)
			}
		}()
	}

sendLoop:
	for _, target := range targets {
		select {
		case <-ctx.Done():
			break sendLoop
		case jobs <- target:
		}
	}
	close(jobs)
	wg.Wait()
}

func pingTarget(ctx context.Context, client *http.Client, target string, maxBodyBytes int64, httpMethod string, useRange bool) {
	start := time.Now()
	method := httpMethod
	if method == "" {
		method = http.MethodGet
	}
	req, err := http.NewRequestWithContext(ctx, method, target, nil)
	if err != nil {
		pingFailure.WithLabelValues(target).Inc()
		log.Printf("[DOWN] %s - request error: %v", target, err)
		return
	}
	req.Header.Set("User-Agent", "iyup-ping-agent")
	if useRange && method == http.MethodGet {
		req.Header.Set("Range", "bytes=0-0")
	}
	resp, err := client.Do(req)
	latency := time.Since(start)
	if err != nil {
		pingFailure.WithLabelValues(target).Inc()
		log.Printf("[DOWN] %s - error: %v", target, err)
		return
	}

	if maxBodyBytes > 0 {
		_, _ = io.Copy(io.Discard, io.LimitReader(resp.Body, maxBodyBytes))
	}
	_ = resp.Body.Close()
	pingLatency.WithLabelValues(target).Observe(latency.Seconds())
	if resp.StatusCode >= http.StatusBadRequest {
		pingFailure.WithLabelValues(target).Inc()
		log.Printf("[DOWN] %s - status: %d, latency: %v", target, resp.StatusCode, latency.Truncate(time.Millisecond))
		return
	}
	pingSuccess.WithLabelValues(target).Inc()
	log.Printf("[UP] %s - status: %d, latency: %v", target, resp.StatusCode, latency.Truncate(time.Millisecond))
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

func loadTargetsFromEnv() []string {
	return parseTargetsEnv(os.Getenv("PING_TARGET_URLS"))
}

func getenvDurationSeconds(name string, fallback int) time.Duration {
	value := getenvInt(name, fallback)
	if value <= 0 {
		value = fallback
	}
	return time.Duration(value) * time.Second
}

func getenvInt(name string, fallback int) int {
	raw := strings.TrimSpace(os.Getenv(name))
	if raw == "" {
		return fallback
	}
	value, err := strconv.Atoi(raw)
	if err != nil || value <= 0 {
		return fallback
	}
	return value
}

func getenvOrDefault(name, fallback string) string {
	value := strings.TrimSpace(os.Getenv(name))
	if value == "" {
		return fallback
	}
	return value
}

func getenvBool(name string, fallback bool) bool {
	raw := strings.TrimSpace(os.Getenv(name))
	if raw == "" {
		return fallback
	}
	value, err := strconv.ParseBool(raw)
	if err != nil {
		return fallback
	}
	return value
}

func defaultTargets() []string {
	return []string{"https://google.com", "https://github.com"}
}
