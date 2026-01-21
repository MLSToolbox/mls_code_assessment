FROM python:3.10-alpine

# Build arguments
ARG ENVIRONMENT=local

WORKDIR /app

# Install Git for repository cloning support
RUN apk add --no-cache git

COPY ./requirements.txt /app
RUN pip3 install -r requirements.txt

COPY ./src /app/src

# Environment variables
ENV EXECUTION_MODE="prod"
ENV ENVIRONMENT=${ENVIRONMENT}
ENV PYTHONPATH=/app/src

WORKDIR /app/src

ENTRYPOINT ["python3"]
CMD ["server.py"]