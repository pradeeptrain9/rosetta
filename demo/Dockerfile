# Self-contained image for the Hugging Face Space.
#
# This deliberately does NOT build FROM rosetta-sandbox: that image exists only
# on a developer's machine, and the Space is built on Hugging Face's
# infrastructure where it cannot be pulled. The GnuCOBOL install is therefore
# repeated here. Keep it in step with the root Dockerfile.
FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc libc6-dev \
 && ( apt-get install -y --no-install-recommends gnucobol4 \
   || apt-get install -y --no-install-recommends gnucobol3 \
   || apt-get install -y --no-install-recommends gnucobol \
   || apt-get install -y --no-install-recommends open-cobol ) \
 && rm -rf /var/lib/apt/lists/*

RUN cobc --version

# Spaces run as uid 1000.
RUN useradd -m -u 1000 user
WORKDIR /app

COPY demo/requirements.txt ./demo/requirements.txt
RUN pip install --no-cache-dir -r demo/requirements.txt

COPY pyproject.toml README.md ./
COPY rosetta ./rosetta
COPY benchmarks ./benchmarks
# Includes demo/precomputed, baked in so the page never needs a live API call.
COPY demo ./demo
RUN pip install --no-cache-dir -e .

RUN chown -R 1000:1000 /app
USER user

# GnuCOBOL is in this image, so the pipeline runs the reference directly rather
# than shelling out to a nested container.
ENV ROSETTA_SANDBOX=local \
    ROSETTA_TEST_VECTORS=40 \
    ROSETTA_MAX_REPAIR_ITERS=3 \
    PORT=7860

EXPOSE 7860
CMD ["uvicorn", "demo.app:app", "--host", "0.0.0.0", "--port", "7860"]
