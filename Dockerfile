# Dockerfile

# Use official Python slim image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy requirements.txt into container
COPY requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy all app code and files into container
COPY . .

# Download yt-dlp only if not already present
RUN [ -f yt-dlp ] || (curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o yt-dlp && chmod +x yt-dlp)

# Ensure /tmp directory exists
RUN mkdir -p /tmp

# Expose app port
EXPOSE 8000

# Startup command: Launch FastAPI with Uvicorn
CMD ["uvicorn", "backend:app", "--host", "0.0.0.0", "--port", "8000"]
