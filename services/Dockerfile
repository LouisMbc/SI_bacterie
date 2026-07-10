FROM python:3.12-slim

WORKDIR /app

COPY common/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY common/bacterie_pb2.py common/bacterie_pb2_grpc.py common/logique_etats.py common/server.py ./

ENV ETAT=stable \
    GRPC_PORT=50051 \
    METRICS_PORT=8000

EXPOSE 50051 8000

CMD ["python", "server.py"]