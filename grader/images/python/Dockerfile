# Sandbox image for Python exercises. Learner code runs here with no network, a read-only
# root filesystem and a non-root user; see backend/src/lattice/infrastructure/sandbox_docker.py.
FROM python:3.15-slim-bookworm AS build
WORKDIR /src
COPY pyproject.toml ./
COPY src ./src
RUN pip wheel --no-cache-dir --wheel-dir /wheels .

FROM python:3.15-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=0 \
    PIP_NO_CACHE_DIR=1 \
    FORGEWAY_GRADING=1
COPY --from=build /wheels /wheels
# The base image ships the standard library without .pyc files and the root filesystem is
# read-only at grading time, so without compileall every interpreter (the harness, the bridge
# child, each run_fresh session and each server a test starts) compiles re, enum, pathlib and
# the rest from source on every start: about 50 ms of the ~55 ms a bare start costs.
RUN pip install --no-cache-dir /wheels/*.whl numpy==2.1.3 \
    && rm -rf /wheels \
    && (pip uninstall -y pip setuptools wheel || true) \
    && python -m compileall -q -j 0 /usr/local/lib/python3.12 \
    && groupadd --gid 10001 grader \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin grader \
    && groupadd --gid 10002 learner \
    && useradd --uid 10002 --gid 10002 --no-create-home --shell /usr/sbin/nologin learner \
    && G=/usr/local/lib/python3.12/site-packages/lattice_grader \
    && chown -R root:10001 "$G" "$G"-*.dist-info \
    && find "$G" "$G"-*.dist-info -type d -exec chmod 0750 {} + \
    && find "$G" "$G"-*.dist-info -type f -exec chmod 0640 {} +
# Two users (ADR 0009). The grader (10001) runs the harness, pytest and the hidden tests. All learner
# code runs as 10002, started by `lattice_grader.launcher` as root. It cannot read or list the
# grader package (root:10001, 0750 and 0640, with no exceptions; what it must run is handed to it
# by the tests) or the hidden tests (0700).
# The runner starts the container as root (`--user 0:0`) with only CAP_SETUID, CAP_SETGID and
# CAP_KILL and no_new_privs; started as anyone else, the launcher refuses to run.
# Every interpreter started with site-packages refuses lattice_grader imports from the submission
# before any learner code runs, with a message saying why.
COPY images/python/lattice_grader_guard.pth /usr/local/lib/python3.12/site-packages/
USER 10001:10001
WORKDIR /work
ENTRYPOINT ["python", "-I", "-m", "lattice_grader.launcher"]
