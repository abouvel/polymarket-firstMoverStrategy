# Use lightweight Python image
FROM python:3.11-slim

# Install system dependencies once
RUN apt-get update && apt-get install -y \
    git \
    curl \
    chromium \
    && rm -rf /var/lib/apt/lists/*

# Set working directory inside the container
WORKDIR /app

# Set environment variables
ENV HF_HOME=/root/.cache/huggingface
ENV PIP_CACHE_DIR=/root/.cache/pip

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download HuggingFace model to cache it
RUN python -c "from langchain_huggingface import HuggingFaceEmbeddings; HuggingFaceEmbeddings(model_name='all-MiniLM-L6-v2')"

# Copy the rest of your code into the container
COPY . .

# Expose port 8000 for FastAPI
EXPOSE 8000

# Default command (will be overridden in docker-compose)
CMD ["python", "main.py"]
