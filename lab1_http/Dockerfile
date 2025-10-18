FROM python:3.12-slim

WORKDIR /app
COPY server.py client.py /app/
COPY www /app/www

EXPOSE 8080
ENV PORT=8080

CMD ["python", "server.py", "/app/www"]
