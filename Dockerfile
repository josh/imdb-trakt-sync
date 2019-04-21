FROM alpine:latest

RUN apk add --no-cache \
  bash \
  ca-certificates \
  curl \
  jq \
  nodejs \
  npm \
  wget

RUN wget -O /usr/bin/tickerd https://github.com/josh/tickerd/releases/latest/download/tickerd-linux-amd64 && chmod +x /usr/bin/tickerd

WORKDIR /app
RUN npm install csvtojson@2.0.8
COPY . .

ENTRYPOINT [ "/usr/bin/tickerd", "--", "/app/main.sh" ]

ENV TICKERD_HEALTHCHECK_FILE "/var/run/healthcheck"
HEALTHCHECK --interval=1m --timeout=3s --start-period=3s --retries=1 \
  CMD [ "/usr/bin/tickerd", "-healthcheck" ]
