# Use lightweight Python image
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your code into the container
COPY . .

# Optional: expose a port (only needed if you're building an API)
# EXPOSE 8000

# Set environment variables (if not using a .env file in production)
# ENV SUPABASE_KEY=your-key
# ENV POLYMARKET_API_KEY=your-api-key

# Command to run your script
CMD ["python", "main.py"]
