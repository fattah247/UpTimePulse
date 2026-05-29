package main

import (
	"reflect"
	"testing"
)

func TestParseTargetsEnv(t *testing.T) {
	t.Parallel()

	targets := parseTargetsEnv(" https://a.example , ,https://b.example ")
	want := []string{"https://a.example", "https://b.example"}
	if !reflect.DeepEqual(targets, want) {
		t.Fatalf("parseTargetsEnv() = %v, want %v", targets, want)
	}
}

func TestLoadTargetsFromEnv(t *testing.T) {
	t.Setenv("PING_TARGET_URLS", "https://one.example,https://two.example")
	want := []string{"https://one.example", "https://two.example"}
	if got := loadTargetsFromEnv(); !reflect.DeepEqual(got, want) {
		t.Fatalf("loadTargetsFromEnv() = %v, want %v", got, want)
	}
}

func TestDefaultTargets(t *testing.T) {
	t.Parallel()

	want := []string{"https://google.com", "https://github.com"}
	if got := defaultTargets(); !reflect.DeepEqual(got, want) {
		t.Fatalf("defaultTargets() = %v, want %v", got, want)
	}
}
