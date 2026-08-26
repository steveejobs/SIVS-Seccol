FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /opt/sivs-worker

COPY tools/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --gid 1200 sivs-worker \
    && useradd --uid 1200 --gid 1200 --no-create-home --shell /usr/sbin/nologin sivs-worker

COPY --chown=1200:1200 tools/tender_portal_worker.py ./tender_portal_worker.py
COPY --chown=1200:1200 tools/tender-agent/viewer.py ./viewer.py

USER 1200:1200

ENTRYPOINT ["python", "/opt/sivs-worker/tender_portal_worker.py"]
CMD ["--execute", "--loop"]
