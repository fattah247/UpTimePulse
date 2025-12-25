package main

import (
	"fmt"
	"net/http"
	"time"
)

func main() {
	target := "https://google.com"

	client := &http.Client{
		Timeout: 10 * time.Second,
	}

	for {
		start := time.Now()
		resp, err := client.Get(target)
		latency := time.Since(start)

		if err != nil {
			fmt.Printf("[DOWN] %s - error: %v\n", target, err)
		} else {
			fmt.Printf("[UP] %s - status: %d, latency: %v\n", target, resp.StatusCode, latency.Truncate(time.Millisecond))
			resp.Body.Close()
		}

		time.Sleep(30 * time.Second)
	}

}
