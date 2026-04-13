FROM python:3.11-slim

LABEL maintainer="KrotPN Telegram Bot"

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot
COPY bot.py .
COPY logs/ ./logs/

# Create logs directory
RUN mkdir -p logs

# Run bot
CMD ["python", "bot.py"]
