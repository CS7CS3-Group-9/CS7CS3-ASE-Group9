FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/backend
ENV PORT=8080
EXPOSE 8080

CMD ["gunicorn", "backend.app:app", "--bind", "0.0.0.0:8080", "--workers", "2"]
