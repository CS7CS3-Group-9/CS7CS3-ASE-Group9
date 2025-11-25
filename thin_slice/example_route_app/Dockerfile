# Use official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy dependencies
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Set environment variable for Cloud Run
ENV PORT=8080

# Expose the port
EXPOSE 8080

# Run app using gunicorn
CMD ["gunicorn", "-b", ":8080", "app:app"]
