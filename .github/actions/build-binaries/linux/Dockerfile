ARG BASE_IMAGE
FROM ${BASE_IMAGE}

ARG PYTHON_VERSION
# myake PYTHON_VERSION a required build argument
RUN test -n "$PYTHON_VERSION"

ENV HOME=/root
RUN uv python install --python-preference=only-managed $PYTHON_VERSION --preview --default
ENV PATH=$HOME/.local/bin:$PATH
RUN uv tool install poetry

VOLUME /src/
WORKDIR /src/
