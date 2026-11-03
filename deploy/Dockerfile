# CRAB runtime image (used by both the gate service and the clean workspace).
FROM docker:cli AS dockercli
FROM python:3.12-slim
COPY --from=dockercli /usr/local/bin/docker /usr/local/bin/docker
COPY pyproject.toml README.md LICENSE NOTICE /opt/crab/
COPY docs/observer-playbook.md /opt/crab/docs/
# the room files the wheel carries (pyproject force-include), named one by one: no local keys or build outputs
COPY deploy/Dockerfile deploy/Dockerfile.clean deploy/cleanroom.yaml deploy/observerroom.yaml deploy/compose.yaml \
     /opt/crab/deploy/
COPY deploy/clean /opt/crab/deploy/clean
COPY deploy/desktop-linux /opt/crab/deploy/desktop-linux
COPY deploy/android-agent/AndroidManifest.xml deploy/android-agent/build.sh /opt/crab/deploy/android-agent/
COPY deploy/android-agent/src /opt/crab/deploy/android-agent/src
COPY src /opt/crab/src
RUN pip install --no-cache-dir /opt/crab
