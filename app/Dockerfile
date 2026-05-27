# --- builder stage: install deps into a venv ---
FROM python:3.12-slim AS builder
WORKDIR /build
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- runtime stage: copy only the venv + app code ---
FROM python:3.12-slim
RUN useradd --create-home --shell /bin/bash app
WORKDIR /home/app
COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app main.py .
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1
USER app
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
