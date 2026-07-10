# Build depuis la racine du repo :
#   docker build -f state-manager/Dockerfile -t bacterie-state-manager:latest .
FROM python:3.12-slim

WORKDIR /app

COPY state-manager/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY common/state_store_pb2.py common/state_store_pb2_grpc.py ./
COPY state-manager/server.py ./

ENV GRPC_PORT=9090 \
    METRICS_PORT=8000 \
    REDIS_HOST=redis \
    REDIS_PORT=6379

EXPOSE 9090 8000

CMD ["python", "server.py"]