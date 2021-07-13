FROM python:3.9-slim-buster

ENV LANG=C.UTF-8 \
  LC_ALL=C.UTF-8 \
  PATH="${PATH}:/root/.poetry/bin"

RUN apt-get update && \
  apt-get install -y --no-install-recommends \
    curl \
    libcairo-dev \
    build-essential \
    libgirepository1.0-dev \
    libgstrtspserver-1.0-dev \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev \
    libgstreamer-plugins-bad1.0-dev \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    gstreamer1.0-doc \
    gstreamer1.0-tools \
  && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY wyze_rtsp_bridge ./wyze_rtsp_bridge
COPY README.md ./

# Install Poetry
RUN curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | POETRY_HOME=/opt/poetry python && \
    cd /usr/local/bin && \
    ln -s /opt/poetry/bin/poetry && \
    poetry config virtualenvs.create false

RUN poetry install
RUN wyze-rtsp-bridge --create-config
CMD mkdir -p /workspace
WORKDIR /workspace

# TODO: figure out some way of copying over tutk library
ENTRYPOINT wyze-rtsp-bridge
