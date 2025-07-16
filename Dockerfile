# Base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies including supervisor
RUN apt-get update && \
    apt-get install -y supervisor && \
    rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . /app

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create logs directory for supervisor logs
RUN mkdir -p /app/logs

# Expose Flask port
EXPOSE 8080

# Run with supervisord
CMD ["supervisord", "-c", "/app/supervisord.conf"]
