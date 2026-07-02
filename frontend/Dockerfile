FROM node:20-alpine

WORKDIR /app

COPY package*.json /app/
RUN npm config set fetch-retries 5 \
  && npm config set fetch-retry-mintimeout 20000 \
  && npm config set fetch-retry-maxtimeout 120000 \
  && npm ci --prefer-offline --no-audit

COPY . /app

CMD ["sh", "-c", "npm run dev -- --host 0.0.0.0 --port ${FRONTEND_PORT:?FRONTEND_PORT not set}"]
