FROM node:8.10

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

ENV NODE_ENV production
COPY package.json package-lock.json /usr/src/app/
RUN npm install && npm cache clean --force
COPY . /usr/src/app

CMD [ "npm", "start" ]
