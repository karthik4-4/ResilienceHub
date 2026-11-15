FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code and configurations
COPY . .

# Install package in editable mode
RUN pip install --no-cache-dir -e .

# Initialize SQLite database and index ChromaDB vector documents
RUN python -m scdrc.cli seed

# Expose FastAPI (8000) and Streamlit (8501)
EXPOSE 8000
EXPOSE 8501

# Default command: launch FastAPI server
CMD ["python", "-m", "scdrc.cli", "serve", "--host", "0.0.0.0", "--port", "8000"]
