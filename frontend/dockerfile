FROM node:12-alpine
ENV VUE_APP_UPLOAD_URL=http://stormspotter-backend:9090/api/upload

WORKDIR /usr/src/app
RUN npm install -g @quasar/cli

COPY dist/spa .
EXPOSE 9091
CMD ["quasar", "serve", "-p", "9091", "--history"]
