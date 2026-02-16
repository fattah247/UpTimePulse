package main

import (
	"context"
	"crypto/tls"
	"errors"
	"io"
	"log"
	"net/http"
	"net/http/httptrace"
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
			Help:    "Total latency of HTTP pings in seconds",
			Buckets: prometheus.DefBuckets,
		},
		[]string{"target"},
	)
	pingUp = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "ping_up",
			Help: "Current target status (1 = up, 0 = down)",
		},
		[]string{"target"},
	)
	pingLastLatency = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "ping_last_latency_seconds",
			Help: "Latency of the most recent ping in seconds",
		},
		[]string{"target"},
	)
	pingSSLCertExpiry = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "ping_ssl_cert_expiry_days",
			Help: "Days until the target's SSL certificate expires",
		},
		[]string{"target"},
	)
	pingDNSDuration = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "ping_dns_duration_seconds",
			Help: "DNS resolution time of the most recent ping",
		},
		[]string{"target"},
	)
	pingConnectDuration = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "ping_connect_duration_seconds",
			Help: "TCP connection time of the most recent ping",
		},
		[]string{"target"},
	)
	pingTLSDuration = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "ping_tls_duration_seconds",
			Help: "TLS handshake time of the most recent ping",
		},
		[]string{"target"},
	)

	allMetrics = []prometheus.Collector{
		pingSuccess, pingFailure, pingLatency, pingUp, pingLastLatency,
		pingSSLCertExpiry, pingDNSDuration, pingConnectDuration, pingTLSDuration,
	}
)

func main() {
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	// Register metrics with optional region constant label.
	// Deploy multiple ping-agents with different PING_REGION values
	// to enable multi-region monitoring in a single Prometheus.
	region := getenvOrDefault("PING_REGION", "")
	if region != "" {
		reg := prometheus.WrapRegistererWith(
			prometheus.Labels{"region": region},
			prometheus.DefaultRegisterer,
		)
		for _, c := range allMetrics {
			reg.MustRegister(c)
		}
	} else {
		for _, c := range allMetrics {
			prometheus.MustRegister(c)
		}
	}

	// Disable keep-alives so each ping measures the full connection
	// lifecycle (DNS + TCP + TLS), matching what a real user experiences.
	transport := http.DefaultTransport.(*http.Transport).Clone()
	transport.DisableKeepAlives = true

	client := &http.Client{
		Timeout:   10 * time.Second,
		Transport: transport,
	}
	pingInterval := getenvDurationSeconds("PING_INTERVAL_SECONDS", 30)
	concurrency := getenvInt("PING_CONCURRENCY", 5)
	maxBodyBytes := int64(getenvInt("PING_BODY_MAX_BYTES", 65536))
	httpMethod := strings.ToUpper(getenvOrDefault("PING_HTTP_METHOD", "GET"))
	useRange := getenvBool("PING_RANGE_REQUEST", true)
	retryCount := getenvInt("PING_RETRY_COUNT", 2)

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
			pingTargets(cycleCtx, client, targets, concurrency, maxBodyBytes, httpMethod, useRange, retryCount)
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
	if region != "" {
		log.Printf("Prometheus metrics available on :8080/metrics (region=%s)", region)
	} else {
		log.Println("Prometheus metrics available on :8080/metrics")
	}

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

func pingTargets(ctx context.Context, client *http.Client, targets []string, concurrency int, maxBodyBytes int64, httpMethod string, useRange bool, retryCount int) {
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
				pingTarget(ctx, client, target, maxBodyBytes, httpMethod, useRange, retryCount)
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

// connTimings captures DNS, TCP, and TLS durations via httptrace.
type connTimings struct {
	dnsStart     time.Time
	connectStart time.Time
	tlsStart     time.Time
	DNS          time.Duration
	Connect      time.Duration
	TLS          time.Duration
}

func newTraceContext(ctx context.Context, t *connTimings) context.Context {
	trace := &httptrace.ClientTrace{
		DNSStart: func(_ httptrace.DNSStartInfo) {
			t.dnsStart = time.Now()
		},
		DNSDone: func(_ httptrace.DNSDoneInfo) {
			if !t.dnsStart.IsZero() {
				t.DNS = time.Since(t.dnsStart)
			}
		},
		ConnectStart: func(_, _ string) {
			t.connectStart = time.Now()
		},
		ConnectDone: func(_, _ string, err error) {
			if !t.connectStart.IsZero() && err == nil {
				t.Connect = time.Since(t.connectStart)
			}
		},
		TLSHandshakeStart: func() {
			t.tlsStart = time.Now()
		},
		TLSHandshakeDone: func(_ tls.ConnectionState, err error) {
			if !t.tlsStart.IsZero() && err == nil {
				t.TLS = time.Since(t.tlsStart)
			}
		},
	}
	return httptrace.WithClientTrace(ctx, trace)
}

func recordTimings(target string, t *connTimings) {
	if t.DNS > 0 {
		pingDNSDuration.WithLabelValues(target).Set(t.DNS.Seconds())
	}
	if t.Connect > 0 {
		pingConnectDuration.WithLabelValues(target).Set(t.Connect.Seconds())
	}
	if t.TLS > 0 {
		pingTLSDuration.WithLabelValues(target).Set(t.TLS.Seconds())
	}
}

func recordSSLCertExpiry(target string, resp *http.Response) {
	if resp.TLS == nil || len(resp.TLS.PeerCertificates) == 0 {
		return
	}
	cert := resp.TLS.PeerCertificates[0]
	days := time.Until(cert.NotAfter).Hours() / 24
	pingSSLCertExpiry.WithLabelValues(target).Set(days)
}

func pingTarget(ctx context.Context, client *http.Client, target string, maxBodyBytes int64, httpMethod string, useRange bool, retryCount int) {
	method := httpMethod
	if method == "" {
		method = http.MethodGet
	}

	attempts := 1 + retryCount
	var lastErr error
	var lastStatus int
	var latency time.Duration
	var timings connTimings

	for attempt := 0; attempt < attempts; attempt++ {
		if attempt > 0 {
			backoff := time.Duration(1<<uint(attempt-1)) * 500 * time.Millisecond
			select {
			case <-ctx.Done():
				break
			case <-time.After(backoff):
			}
		}

		timings = connTimings{}
		start := time.Now()
		req, err := http.NewRequestWithContext(ctx, method, target, nil)
		if err != nil {
			latency = time.Since(start)
			lastErr = err
			continue
		}
		req.Header.Set("User-Agent", "iyup-ping-agent")
		if useRange && method == http.MethodGet {
			req.Header.Set("Range", "bytes=0-0")
		}

		// Attach httptrace to capture DNS/TCP/TLS timings
		req = req.WithContext(newTraceContext(req.Context(), &timings))

		resp, err := client.Do(req)
		latency = time.Since(start)

		if err != nil {
			lastErr = err
			log.Printf("[RETRY] %s - attempt %d/%d error: %v", target, attempt+1, attempts, err)
			continue
		}

		if maxBodyBytes > 0 {
			_, _ = io.Copy(io.Discard, io.LimitReader(resp.Body, maxBodyBytes))
		}
		_ = resp.Body.Close()

		if resp.StatusCode >= http.StatusInternalServerError {
			lastStatus = resp.StatusCode
			lastErr = nil
			log.Printf("[RETRY] %s - attempt %d/%d status: %d", target, attempt+1, attempts, resp.StatusCode)
			continue
		}

		// Non-retryable result (success or 4xx client error)
		pingLatency.WithLabelValues(target).Observe(latency.Seconds())
		pingLastLatency.WithLabelValues(target).Set(latency.Seconds())
		recordTimings(target, &timings)
		recordSSLCertExpiry(target, resp)

		if resp.StatusCode >= http.StatusBadRequest {
			pingFailure.WithLabelValues(target).Inc()
			pingUp.WithLabelValues(target).Set(0)
			log.Printf("[DOWN] %s - status: %d, latency: %v", target, resp.StatusCode, latency.Truncate(time.Millisecond))
		} else {
			pingSuccess.WithLabelValues(target).Inc()
			pingUp.WithLabelValues(target).Set(1)
			log.Printf("[UP] %s - status: %d, latency: %v (dns=%v tcp=%v tls=%v)",
				target, resp.StatusCode, latency.Truncate(time.Millisecond),
				timings.DNS.Truncate(time.Microsecond),
				timings.Connect.Truncate(time.Microsecond),
				timings.TLS.Truncate(time.Microsecond))
		}
		return
	}

	// All attempts exhausted — record failure
	pingLatency.WithLabelValues(target).Observe(latency.Seconds())
	pingLastLatency.WithLabelValues(target).Set(latency.Seconds())
	recordTimings(target, &timings)
	pingFailure.WithLabelValues(target).Inc()
	pingUp.WithLabelValues(target).Set(0)
	if lastErr != nil {
		log.Printf("[DOWN] %s - all %d attempts failed: %v, latency: %v", target, attempts, lastErr, latency.Truncate(time.Millisecond))
	} else {
		log.Printf("[DOWN] %s - all %d attempts failed: status %d, latency: %v", target, attempts, lastStatus, latency.Truncate(time.Millisecond))
	}
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
