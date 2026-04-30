# =============================================================================
# MintPy Docker Playbook — Dockerfile
# Extends the official MintPy container with Jupyter, plotting libs, and utils
# =============================================================================
FROM ghcr.io/insarlab/mintpy:latest

LABEL maintainer="MintPy Docker Playbook"
LABEL description="Complete MintPy InSAR time-series analysis environment"

# Switch to root for system installs
USER root

# Install system utilities for data download and archive handling
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    curl \
    xz-utils \
    make \
    && rm -rf /var/lib/apt/lists/*

# Switch back to mambauser (the default MintPy container user)
USER mambauser

# Install additional Python packages for analysis and visualization
RUN micromamba install -y -n base -c conda-forge \
    jupyterlab \
    notebook \
    matplotlib \
    plotly \
    cartopy \
    ipywidgets \
    ipympl \
    h5py \
    pandas \
    seaborn \
    cmcrameri \
    && micromamba clean -afy

# Set up workspace
WORKDIR /workspace

# Copy project files
COPY --chown=mambauser:mambauser config/ /workspace/config/
COPY --chown=mambauser:mambauser scripts/ /workspace/scripts/
COPY --chown=mambauser:mambauser notebooks/ /workspace/notebooks/

# Make scripts executable
RUN chmod +x /workspace/scripts/*.sh

# Environment variables
ENV MINTPY_HOME=/opt/conda/lib/python3.11/site-packages/mintpy
ENV PYTHONDONTWRITEBYTECODE=1
ENV MPLBACKEND=Agg

# Default working directory for MintPy processing
WORKDIR /data

# Entrypoint
COPY --chown=mambauser:mambauser scripts/entrypoint.sh /workspace/scripts/entrypoint.sh
ENTRYPOINT ["/workspace/scripts/entrypoint.sh"]
CMD ["bash"]
