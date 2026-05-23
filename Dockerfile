FROM python:3.13-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV HERMES_TRADING_MODE=paper

COPY pyproject.toml README.md ./
COPY src ./src
COPY state ./default_state

RUN pip install --no-cache-dir -e .

CMD ["python", "-m", "eurusd_bot.worker"]
