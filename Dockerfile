# Base Image
FROM python:3.12-slim AS base

# Environment Variables
ENV PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    PYTHONUNBUFFERED=1

# Builder Stage
FROM base as builder

# Install Dependencies for Building
RUN apt-get update && \
    apt-get install --no-install-suggests --no-install-recommends --yes gcc libhdf5-dev pkg-config

RUN python -m venv /venv


# Install Dependencies into Virtual Environment
RUN /venv/bin/pip install --no-cache-dir --upgrade pip setuptools && \
    /venv/bin/pip install marshmallow==3.19.0 && \
    /venv/bin/pip install azure-ai-ml --upgrade && \
    /venv/bin/pip install .



# Set Working Directory
WORKDIR /code

# Copy Application Code
COPY /src/omnia_timeseries ./src
COPY ./setup.py ./

# Upgrade pip and Install Dependencies from setup.py
RUN pip install --upgrade pip setuptools wheel && \
    pip install .

# Create Virtual Environment

# Runner Stage
FROM base AS runner

# Create a Non-Root User
RUN groupadd -g 1000 aion && \
    useradd -r -u 1000 -g aion aion

# Copy Virtual Environment from Builder
COPY --from=builder /venv /opt/venv

# Update Path to Use Virtual Environment
ENV PATH="/opt/venv/bin:${PATH}"

# Set User
USER 1000

# Default Command
CMD ["python"]
