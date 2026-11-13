# Voltrix VX-200 support bot: container image (spec 08 section 6, Session D).
#
# Build with:  deploy/build_image.sh   (see deploy/README.md)
#
# Two stages:
#   builder  installs requirements.txt exactly as CI does, downloads the
#            pinned embedding model, builds the index of the active KB
#            version with the CI command, and checks its manifest.
#   runtime  the app, the venv, the model and that one index. Runs as
#            uid 1000 on port 8080, with no model downloads at run time.
#
# Pins (checked 2026-11-12):
# - python:3.14.10-slim-trixie, multi-arch index digest (same patch as CI).
# - AWS Lambda Web Adapter 1.1.0 (latest release, README "Docker Images"),
#   manifest list digest. On the laptop it is never started: it is a Lambda
#   extension in /opt/extensions, and only the Lambda runtime starts those.
# Architecture: x86_64 (spec 08 section 6).

FROM --platform=linux/amd64 public.ecr.aws/awsguru/aws-lambda-adapter:1.1.0@sha256:17cfd08eff1dfea3f6a9a1e9c65fdac80aa4919b6085e746615530f43f57d2f1 AS lambda-adapter

# ---------------------------------------------------------------------------
FROM --platform=linux/amd64 python:3.14.10-slim-trixie@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    HF_HOME=/opt/hf

RUN python -m venv /opt/venv
WORKDIR /app

# requirements.txt as pinned, CPU-only torch (the file carries the
# PyTorch CPU index), exactly as CI installs it (spec 06, Round 2 Q1).
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY deploy/check_pins.py deploy/
RUN python deploy/check_pins.py requirements.txt

# The pinned model (spec 01), downloaded with the project's own loader, so
# the name and revision come only from ingestion/config.py.
COPY ingestion/ ingestion/
RUN python -c "from ingestion.embedding import load_model, load_token_counter; load_model(); load_token_counter()"

# From here on the model hub is off: the index build proves the model
# files in the image are complete.
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

# The index of the active KB version only, built with the command and the
# reader CI uses (.github/actions/setup-bot), then its manifest is checked.
COPY query/ query/
COPY data/ data/
COPY .github/scripts/active_kb_version.py .github/scripts/
COPY deploy/check_manifest.py deploy/
RUN active="$(python .github/scripts/active_kb_version.py)" \
 && python -m ingestion.build "$active" \
 && python deploy/check_manifest.py "$active" \
 && chmod -R a+rX /opt/hf /app/indexes

# ---------------------------------------------------------------------------
FROM --platform=linux/amd64 python:3.14.10-slim-trixie@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    HF_HOME=/opt/hf \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    AWS_LWA_PORT=8080 \
    AWS_LWA_READINESS_CHECK_PATH=/health

COPY --from=lambda-adapter /lambda-adapter /opt/extensions/lambda-adapter

# Non-root user, uid 1000. The secrets file is mounted read-only at
# /home/app/.config/voltrix/secrets.env (spec 08 section 5).
RUN groupadd --gid 1000 app \
 && useradd --uid 1000 --gid 1000 --create-home --home-dir /home/app --shell /usr/sbin/nologin app \
 && install -d -o app -g app -m 700 /home/app/.config /home/app/.config/voltrix

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/hf /opt/hf

WORKDIR /app
COPY --from=builder /app/indexes/ indexes/
COPY data/ACTIVE_KB_VERSION data/ACTIVE_KB_VERSION
COPY ingestion/ ingestion/
COPY query/ query/
COPY web/ web/

# The app code is read-only for the app user; handoffs/ is its only
# writable folder (on Lambda, HANDOFF_DIR=/tmp/handoffs instead).
RUN python -m compileall -q ingestion query web \
 && install -d -o app -g app -m 755 handoffs

# Build record (Round 2 Q1): commit, date and the installed packages.
# Placed last so a new date or commit never invalidates the layers above.
ARG GIT_COMMIT=unknown
ARG GIT_TREE=unknown
ARG BUILD_DATE=unknown
RUN { \
      echo "git_commit: ${GIT_COMMIT}"; \
      echo "git_tree: ${GIT_TREE}"; \
      echo "build_date: ${BUILD_DATE}"; \
      echo "kb_version: $(cat data/ACTIVE_KB_VERSION)"; \
      echo "python: $(python -c 'import platform; print(platform.python_version())')"; \
      echo "base_image: python:3.14.10-slim-trixie@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f"; \
      echo "lambda_adapter: public.ecr.aws/awsguru/aws-lambda-adapter:1.1.0@sha256:17cfd08eff1dfea3f6a9a1e9c65fdac80aa4919b6085e746615530f43f57d2f1"; \
      echo "pip_freeze:"; \
      pip freeze --all; \
    } > BUILD_INFO.txt \
 && chmod 644 BUILD_INFO.txt
LABEL org.opencontainers.image.title="voltrix-support-bot" \
      org.opencontainers.image.revision="${GIT_COMMIT}" \
      org.opencontainers.image.created="${BUILD_DATE}"

USER app
EXPOSE 8080
CMD ["python", "-m", "web"]
