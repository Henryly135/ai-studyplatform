FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install --no-install-recommends -y ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY services/learning-service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY packages/platform_common /packages/platform_common
RUN pip install --no-cache-dir -e /packages/platform_common

COPY services/learning-service/app /app/app

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${LEARNING_PORT:?LEARNING_PORT not set} --reload"]
