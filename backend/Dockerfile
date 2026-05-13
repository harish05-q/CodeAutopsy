FROM python:3.12-slim

WORKDIR /app

# Install git (needed for cloning repos)
RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

# Copy and install dependencies first (Docker layer caching)
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy backend source code + root __init__ for module resolution
COPY backend/ ./backend/

# Create data directory
RUN mkdir -p /app/data

EXPOSE 8000

# Run from /app so "backend.main" resolves correctly
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
