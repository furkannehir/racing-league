# Use the official Python image from the Docker Hub
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Set the PYTHONPATH environment variable
ENV PYTHONPATH=/app

# List the contents of the /app/src/config directory for debugging
RUN ls -la /app/src/config

# Expose the port the app runs on
EXPOSE 5000

# Migrate once before any Gunicorn workers import the application.
ENTRYPOINT ["python", "scripts/start_server.py"]

# Allow deployment platforms to override Gunicorn arguments through CMD.
CMD ["gunicorn"]
