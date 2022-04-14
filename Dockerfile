FROM python:3.9-slim as common-base

# Builder image
FROM common-base as builder

RUN pip install -U pip setuptools

RUN mkdir -p /app
WORKDIR /app

RUN apt-get update && \
  apt-get install -y build-essential python3-dev && \
  rm -rf /var/lib/apt/lists/*

RUN mkdir -p /install

COPY requirements.txt ./
RUN sh -c 'pip install --no-warn-script-location --prefix=/install -r requirements.txt'

# Final image, just copy over pre-compiled files
FROM common-base

RUN mkdir -p /app
WORKDIR /app

COPY app.py ./app.py
COPY defi ./defi
COPY settings ./settings
COPY --from=builder /install /usr/local

EXPOSE 80

ARG CI_COMMIT_SHA
LABEL git-commit=$CI_COMMIT_SHA
LABEL project=qset

CMD ["python3", "app.py"]
