# Build stage
FROM golang:1.23-alpine AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY main.go .
RUN CGO_ENABLED=0 go build -o /out/ping-agent ./main.go

# Runtime stage
FROM alpine:3.19
RUN apk add --no-cache ca-certificates
COPY --from=build /out/ping-agent /usr/local/bin/ping-agent
CMD ["ping-agent"]
