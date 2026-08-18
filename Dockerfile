FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SIVS_HOST=0.0.0.0 \
    SIVS_PORT=8844 \
    SIVS_DB=/data/sivs.db \
    SIVS_REQUIRE_PERSISTENT_DB=1 \
    SIVS_TRUST_PROXY=1 \
    SIVS_SECURE_COOKIE=1

WORKDIR /app

COPY requirements.txt ./requirements.txt
COPY sivs_2_2/requirements.txt ./sivs_2_2/requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY sivs_2_2 ./sivs_2_2
COPY tools/reset_sivs_password.py ./tools/reset_sivs_password.py
RUN mkdir -p /data \
    && useradd --system --uid 10001 --create-home sivs \
    && chown -R sivs:sivs /app /data

USER sivs

EXPOSE 8844
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import json,os,urllib.request; port=os.environ.get('PORT') or os.environ.get('SIVS_PORT','8844'); response=urllib.request.urlopen('http://127.0.0.1:'+port+'/api/status',timeout=3); assert response.status == 200 and json.load(response).get('ok')" || exit 1

CMD ["python", "sivs_2_2/server.py"]
