# Use official Python base image (Linux, for best compatibility)
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose MCP server port (if needed)
EXPOSE 8765

# Default: run the GUI (change to mcp_server.py for headless/server)
CMD ["python", "main.py"]
