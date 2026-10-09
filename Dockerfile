# Differential-execution sandbox: GnuCOBOL (the ground-truth compiler) plus
# CPython, with no network. Generated code never runs on the host.
FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive

# cobc shells out to a C compiler, so gcc and libc headers are required
# alongside GnuCOBOL itself. Package naming varies across Debian releases.
RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc libc6-dev \
 && ( apt-get install -y --no-install-recommends gnucobol4 \
   || apt-get install -y --no-install-recommends gnucobol3 \
   || apt-get install -y --no-install-recommends gnucobol \
   || apt-get install -y --no-install-recommends open-cobol ) \
 && rm -rf /var/lib/apt/lists/*

RUN cobc --version && python3 --version

# Generated programs run as an unprivileged user inside the container.
RUN useradd -m -u 10001 rosetta
USER rosetta

WORKDIR /work
CMD ["python3", "/work/driver.py"]
