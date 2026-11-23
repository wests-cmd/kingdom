# Disposable Linux native-desktop isolation proof only; NOT a product worker.
# The runtime is started by CI with --network none, --read-only,
# --cap-drop ALL, --security-opt no-new-privileges, no host mounts and no ports.
FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    HOME=/tmp \
    DISPLAY=:99 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-tk python3-pil \
      xvfb xdotool x11-utils x11-apps netpbm fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --create-home --shell /usr/sbin/nologin kingdom-demo \
    && install -d -m 0755 /opt/kingdom

COPY --chmod=0755 start.sh /opt/kingdom/start.sh
COPY --chmod=0644 demo.py probe.py /opt/kingdom/

USER 10001:10001
WORKDIR /opt/kingdom
ENTRYPOINT ["/opt/kingdom/start.sh"]
