FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY services/identity-service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY packages/platform_common /packages/platform_common
RUN pip install --no-cache-dir -e /packages/platform_common

COPY services/identity-service/app /app/app

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${IDENTITY_PORT:?IDENTITY_PORT not set} --reload"]
