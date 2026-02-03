FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install deps first
COPY ./requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY ./ /app/

# Non-root user
RUN useradd -m appuser
USER appuser

EXPOSE 8080

# Start the API server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
