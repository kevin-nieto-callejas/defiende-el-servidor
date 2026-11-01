# API de simulación para un Hugging Face Space con Docker (u otro host con contenedores).
# El contexto de construcción sale de deploy/api/empaquetar.py: incluye código, manifiestos y pesos.
FROM python:3.14-slim

ENV PIP_NO_CACHE_DIR=1 OMP_NUM_THREADS=2 RALLY_MODELOS=/app/pesos
RUN useradd -m rally
WORKDIR /app

COPY requirements-api.txt .
RUN pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements-api.txt

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-deps .

COPY manifests ./manifests
COPY pesos ./pesos
USER rally

EXPOSE 7860
CMD ["uvicorn", "rally.api:app", "--host", "0.0.0.0", "--port", "7860"]
