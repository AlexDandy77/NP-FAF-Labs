FROM python:3.11-slim
WORKDIR /app
COPY . /app
EXPOSE 8080
ENV HOST=0.0.0.0 PORT=8080 USE_LOCK=1 RATE_LIMIT=5 WINDOW_SEC=1.0 PYTHONPATH=/app
CMD ["python", "lab2_concurrent_http/server_mt.py", "lab1_http/www"]