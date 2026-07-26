FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Run the bot (we set pythonpath to root so modules are resolved properly)
ENV PYTHONPATH=/app
CMD ["python", "bot/main.py"]
