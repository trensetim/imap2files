FROM python:3-alpine

# ===== Dependencies =====
COPY --chown=1000:1000 src/build/python/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ===== Install Application =====
WORKDIR /app
COPY --chown=1000:1000 src/main/python/ /app/bin
COPY --chown=1000:1000 src/main/resources/templates /app/templates

RUN mkdir -p /app/output /app/cache && \
    chown -R 1000:1000 /app/output /app/cache && \
    chmod -R a+rw /app/output /app/cache
VOLUME /app/output
VOLUME /app/cache

# ===== Base Configuration =====
ENV templates_base_dir=/app/templates
ENV output_base_dir=/app/output
ENV cache_path=/app/cache/imap2files.cachedb

# ===== Container Settings =====
USER 1000:1000
STOPSIGNAL SIGTERM
ENTRYPOINT [ "python", "/app/bin/main.py" ]
