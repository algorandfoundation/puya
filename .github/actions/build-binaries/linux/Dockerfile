# Modified from https://github.com/oleksis/pyinstaller-manylinux

ARG BASE_IMAGE=quay.io/pypa/manylinux_2_28_x86_64
FROM ${BASE_IMAGE} AS builder

LABEL org.opencontainers.image.description="Run PyInstaller on ManyLinux 2.28 (AlmaLinux 8.7 based)"
LABEL org.opencontainers.image.licenses=MIT

SHELL ["/bin/bash", "-c"]

ARG HOME=/root
ARG PYTHON_VERSION
ARG OPENSSL_VERSION=openssl-1.1.1u
ARG OPENSSL_DIR=/usr/local/ssl
ARG PYENV_ROOT="${HOME}/.pyenv"

# myake PYTHON_VERSION a required build argument
RUN test -n "$PYTHON_VERSION"

ENV PYTHON_VERSION=${PYTHON_VERSION} \
    OPENSSL_VERSION=${OPENSSL_VERSION} \
    OPENSSL_DIR=${OPENSSL_DIR} \
    PYENV_ROOT="${PYENV_ROOT}" \
    PATH="${PYENV_ROOT}/bin:${PYENV_ROOT}/shims:${OPENSSL_DIR}/bin:$PATH" \
    PYPI_URL=https://pypi.python.org/ \
    PYPI_INDEX_URL=https://pypi.python.org/simple \
    HOME=${HOME}

# Install build dependencies and clean up
RUN dnf -y install --allowerasing make gcc zlib-devel bzip2 bzip2-devel \
    readline-devel sqlite sqlite-devel tk-devel libffi-devel xz-devel \
    libuuid-devel gdbm-devel libnsl2-devel git && \
    dnf clean all

# Build and install custom OpenSSL
RUN set -exuo pipefail && \
    yum erase -y openssl-devel && \
    curl -s -L -o ${OPENSSL_VERSION}.tar.gz https://www.openssl.org/source/${OPENSSL_VERSION}.tar.gz && \
    tar -xzf ${OPENSSL_VERSION}.tar.gz && \
    cd ${OPENSSL_VERSION} && \
    ./config no-shared --prefix=${OPENSSL_DIR} --openssldir=${OPENSSL_DIR} \
       CPPFLAGS="-Wdate-time -D_FORTIFY_SOURCE=2" \
       CFLAGS="-g -O2 -Wall -fdebug-prefix-map=/=. -fstack-protector-strong -Wformat -Werror=format-security -fPIC" \
       CXXFLAGS="-g -O2 -Wall -fdebug-prefix-map=/=. -fstack-protector-strong -Wformat -Werror=format-security -fPIC" \
       LDFLAGS="-Wl,-Bsymbolic-functions -Wl,-z,relro -Wl,-z,now -fPIC" && \
    make -j$(nproc) > /dev/null && \
    make install_sw > /dev/null && \
    cd .. && \
    rm -rf ${OPENSSL_VERSION} ${OPENSSL_VERSION}.tar.gz

# Install pyenv and Python without sourcing bashrc
RUN set -exuo pipefail && \
    git clone https://github.com/pyenv/pyenv.git ${PYENV_ROOT} && \
    cd ${PYENV_ROOT} && git checkout master && \
    CPPFLAGS="-O2 -I${OPENSSL_DIR}/include" \
    CFLAGS="-I${OPENSSL_DIR}/include" \
    LD_FLAGS="-L${OPENSSL_DIR}/lib -Wl,-rpath,${OPENSSL_DIR}/lib" \
    LD_RUN_PATH="${OPENSSL_DIR}/lib" \
    CONFIGURE_OPTS="--with-openssl=${OPENSSL_DIR}" \
    PYTHON_CONFIGURE_OPTS="--enable-shared" \
    ${PYENV_ROOT}/bin/pyenv install ${PYTHON_VERSION} && \
    ${PYENV_ROOT}/bin/pyenv global ${PYTHON_VERSION}

# Install Python packages
RUN set -exuo pipefail && \
    ${PYENV_ROOT}/shims/pip install --no-cache-dir --upgrade pip setuptools wheel && \
    ${PYENV_ROOT}/shims/pip install --no-cache-dir poetry

# Clean up
RUN set -exuo pipefail && \
    dnf -y remove gcc make git && \
    dnf clean all && \
    rm -rf /var/cache/yum /tmp/* && \
    rm -rf ${PYENV_ROOT}/cache/* ${PYENV_ROOT}/src/*

# Now create a smaller runtime image
FROM ${BASE_IMAGE} AS runtime

ARG HOME=/root
ARG OPENSSL_DIR=/usr/local/ssl
ARG PYENV_ROOT="${HOME}/.pyenv"

ENV PATH="${PYENV_ROOT}/bin:${PYENV_ROOT}/shims:${OPENSSL_DIR}/bin:$PATH" \
    PYENV_ROOT="${PYENV_ROOT}" \
    HOME=${HOME}

# Install minimal runtime dependencies
RUN dnf -y install zlib bzip2 readline sqlite tk libffi libnsl2 libuuid gdbm && \
    dnf clean all && \
    rm -rf /var/cache/yum && \
    mkdir -p /src/

# Copy only the necessary files from the builder stage
COPY --from=builder ${OPENSSL_DIR} ${OPENSSL_DIR}
COPY --from=builder ${PYENV_ROOT} ${PYENV_ROOT}

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

VOLUME /src/
WORKDIR /src/

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
