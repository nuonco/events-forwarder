# Stage 1: Get the OTel Collector binary
FROM otel/opentelemetry-collector-contrib:latest AS otel-builder

# Stage 2: Build the final application image
FROM python:3.11-slim

# Copy OTel Collector binary from builder stage
COPY --from=otel-builder /otelcol-contrib /usr/local/bin/otelcol

# Set working directory inside the container
WORKDIR /app

# Copy requirements file first (for better layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire application code (includes otel-collector/config.yaml)
COPY . .

# Expose ports
EXPOSE 8080
EXPOSE 4318
EXPOSE 4317

# Default command runs FastAPI app
# fly.toml overrides this to run both app and collector processes
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
