# Use official OpenTelemetry Collector image
FROM otel/opentelemetry-collector-contrib:latest

# Copy configuration file
COPY config.yaml /etc/otelcol/config.yaml

# Expose ports for receiving telemetry
EXPOSE 4318  # OTLP HTTP receiver
EXPOSE 4317  # OTLP gRPC receiver

# Run the collector with our config
CMD ["--config=/etc/otelcol/config.yaml"]
