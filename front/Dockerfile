FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# URL da API vista pelo navegador (embutida no bundle no build)
ARG VITE_API_URL=http://localhost:8000
ARG VITE_DAGSTER_URL=http://localhost:3000
ENV VITE_API_URL=$VITE_API_URL VITE_DAGSTER_URL=$VITE_DAGSTER_URL
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/build/client /usr/share/nginx/html
EXPOSE 80
