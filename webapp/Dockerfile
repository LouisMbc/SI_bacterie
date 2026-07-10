# Build depuis la racine du repo :
#   docker build -f webapp/Dockerfile -t bacterie-webapp:latest .
FROM python:3.12-slim

WORKDIR /app

COPY webapp/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY common/bacterie_pb2.py common/bacterie_pb2_grpc.py ./
COPY webapp/app.py ./
COPY webapp/templates ./templates

ENV PORT=5000
EXPOSE 5000

CMD ["python", "app.py"]