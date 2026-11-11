# VeVeMP3 Oracle Worker

Prepared for a free-tier ARM Linux VM. This folder contains no credentials.

Build: `docker build -t vevemp3-worker .`

Run only behind a TLS reverse proxy; do not expose port 8765 publicly. Supply `VEVEMP3_LOCAL_WORKER_TOKEN` as a server-side environment secret, matching the Render `VEVEMP3_WORKER_TOKEN`. Configure a stable HTTPS worker URL in Render only after testing `/healthz`, `/info` and `/convert` on authorized content. YouTube access from Oracle Cloud is not guaranteed.

No Oracle instance has been created yet.
