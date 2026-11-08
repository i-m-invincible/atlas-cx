FROM node:24.17.0-alpine@sha256:156b55f92e98ccd5ef49578a8cea0df4679826564bad1c9d4ef04462b9f0ded6 AS build
WORKDIR /app
COPY package.json package-lock.json .npmrc ./
COPY frontend/package.json ./frontend/
RUN npm ci
COPY frontend ./frontend
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.28.0-alpine@sha256:c97ff0bf7cbae369953c6da1232ec14ad9f971d66360c5698db0856a4cd657a0
COPY infra/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/frontend/dist /usr/share/nginx/html
USER 101:101
EXPOSE 8080
