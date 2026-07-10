FROM python:3.12-slim

WORKDIR /app

COPY webapp/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY common/bacterie_pb2.py common/bacterie_pb2_grpc.py ./
COPY common/state_store_pb2.py common/state_store_pb2_grpc.py ./
COPY webapp/app.py webapp/state_client.py ./
COPY webapp/templates ./templates

ENV PORT=5000
EXPOSE 5000

CMD ["python", "app.py"]