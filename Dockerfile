FROM node:8.10

RUN wget -O /usr/bin/tickerd https://github.com/josh/tickerd/releases/latest/download/tickerd-linux-amd64 && chmod +x /usr/bin/tickerd

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

ENV NODE_ENV production
COPY package.json package-lock.json /usr/src/app/
RUN npm install && npm cache clean --force
COPY . /usr/src/app

ENTRYPOINT [ "/usr/bin/tickerd", "--", "node", "./index.js" ]

ENV TICKERD_HEALTHCHECK_FILE "/var/run/healthcheck"
HEALTHCHECK --interval=1m --timeout=3s --start-period=3s --retries=1 \
  CMD [ "/usr/bin/tickerd", "-healthcheck" ]
