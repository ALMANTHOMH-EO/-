FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    EO_VAULT_DIR=/srv/alm/vault \
    EO_VAULT_RUNTIME_DIR=/run/eo-runtime
WORKDIR /srv/alm
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --system --gid 10001 alm \
    && useradd --system --uid 10001 --gid alm --home-dir /nonexistent --shell /usr/sbin/nologin alm \
    && mkdir -p /srv/alm/vault /run/eo-runtime \
    && chown -R alm:alm /srv/alm /run/eo-runtime
# Only the encrypted payload and minimal signed-loader components enter the image.
COPY --chown=alm:alm vault/ /srv/alm/vault/
COPY --chown=alm:alm eo_vault_runtime.py vault_bootstrap.py /srv/alm/
USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["python", "/srv/alm/vault_bootstrap.py"]
