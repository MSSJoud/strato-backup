FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MPLCONFIGDIR=/tmp/matplotlib

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    g++ \
    git \
    curl \
    ca-certificates \
    libgdal-dev \
    gdal-bin \
    libproj-dev \
    proj-bin \
    libgeos-dev \
    libhdf5-dev \
    libnetcdf-dev \
    libopenblas-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY pyproject.toml README.md /workspace/
COPY src /workspace/src
COPY app /workspace/app
COPY configs /workspace/configs
COPY docs /workspace/docs
COPY examples /workspace/examples
COPY scripts /workspace/scripts

RUN pip install --upgrade pip setuptools wheel && pip install -e .

ENTRYPOINT ["/workspace/app/entrypoint.sh"]
CMD ["bash"]

