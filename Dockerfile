FROM python:3.14-slim
WORKDIR /app
COPY pyproject.toml .
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip pip install --upgrade pip
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt
COPY apps/__init__.py /app/apps/__init__.py
COPY apps/api /app/apps/api
COPY jobs /app/jobs
CMD ["uvicorn", "apps.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
