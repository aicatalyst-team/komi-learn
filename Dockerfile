FROM registry.access.redhat.com/ubi9/python-312

WORKDIR /opt/app-root/src

# Install git (needed by pool module for git operations)
USER 0
RUN dnf install -y git && dnf clean all
USER 1001

# Copy dependency specification first for layer caching
COPY pyproject.toml .
COPY komi/__init__.py komi/__init__.py

# Install the package with dev dependencies (includes pytest for testing)
RUN pip install --no-cache-dir -e ".[dev]"

# Copy the full application source
COPY . .

# Re-install to pick up all source files
RUN pip install --no-cache-dir -e ".[dev]"

# OpenShift compatibility: arbitrary UID support
RUN chgrp -R 0 /opt/app-root && chmod -R g=u /opt/app-root

# No EXPOSE - CLI tool, no ports

USER 1001

ENTRYPOINT ["komi-learn"]
CMD ["--help"]
