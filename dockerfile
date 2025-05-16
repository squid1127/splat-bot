# Use the official Python image from the Docker Hub
FROM python:alpine3.20

# Install Alpine dependencies
RUN apk add --no-cache \
    gcc musl-dev libffi-dev openssl-dev cargo make g++

# Set the working directory in the container
WORKDIR /app

# Copy only the requirements files first to leverage Docker cache
COPY ./src/core/requirements.txt ./src/core/requirements.txt
COPY ./requirements.txt requirements.txt

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r ./src/core/requirements.txt \
    && pip install --no-cache-dir -r ./requirements.txt

# Copy the rest of the application code
COPY . .

# Run app.py when the container launches
CMD ["python", "./src/app.py"]
