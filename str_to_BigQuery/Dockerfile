# Use a Python base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED True

# Copy application files
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Cloud Run defaults to listen on port 8080
ENV PORT 8080

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]