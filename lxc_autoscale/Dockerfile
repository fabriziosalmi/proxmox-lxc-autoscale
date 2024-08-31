# Start with a base image
FROM python:3.9-slim

# Set environment variables (if needed)
ENV POLL_INTERVAL=300
ENV CPU_UPPER_THRESHOLD=80
ENV CPU_LOWER_THRESHOLD=20

# Create a directory for the app
WORKDIR /app

# Copy the application files to the container
COPY lxc_autoscale /app/

# Install Python dependencies
RUN pip install --no-cache-dir -r /app/requirements.txt

# Set up SSH (if needed)
RUN apt-get update && apt-get install -y openssh-client && rm -rf /var/lib/apt/lists/*

# Set the entry point to run your application
ENTRYPOINT ["python", "/app/lxc_autoscale.py"]
