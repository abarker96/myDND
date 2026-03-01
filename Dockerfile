# Flask app only - MongoDB runs as a separate service (see docker-compose.yml)
FROM python:3.12-slim

# Create a non-root user to run the app
RUN useradd --create-home appuser

WORKDIR /app

# Install system dependencies in a single layer
RUN apt-get update \
  && apt-get install -y --no-install-recommends curl \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

# Install Python dependencies from pinned requirements file
COPY requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy app files
COPY --chown=appuser:appuser app.py /app/app.py
COPY --chown=appuser:appuser ./res/ /res/
COPY --chown=appuser:appuser ./templates /app/templates
COPY --chown=appuser:appuser ./static /app/static

# Switch to non-root user
USER appuser

EXPOSE 5000

# Healthcheck targets the Flask app
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl --silent --fail http://localhost:5000 || exit 1

CMD ["python3", "/app/app.py"]
