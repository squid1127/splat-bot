# Use the official Python image from the Docker Hub
FROM python:3.12.1-slim

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
