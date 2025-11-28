FROM python:3.11-slim

WORKDIR /app

# Install uv for fast package management
RUN pip install uv

# Copy project files
COPY pyproject.toml .
COPY app/ app/

# Install dependencies
RUN uv pip install --system -e .

# Expose port
EXPOSE 8001

# Run server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
