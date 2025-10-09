FROM python:3.10-alpine

WORKDIR /app

COPY ./requirements.txt /app
RUN pip3 install -r requirements.txt

COPY ./src /app/src

ENV EXECUTION_MODE="prod"
ENV PYTHONPATH=/app/src

WORKDIR /app/src

ENTRYPOINT ["python3"]
CMD ["server.py"]