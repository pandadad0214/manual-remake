FROM apify/actor-python:3.13
USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*
USER myuser
COPY --chown=myuser:myuser requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=myuser:myuser . ./
RUN python3 -m compileall -q src/
CMD ["python3", "-m", "src"]
