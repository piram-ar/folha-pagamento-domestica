# Etapa 1: build do React
FROM node:22-alpine AS build
WORKDIR /app
# Limita o heap do Node para o build caber no 1 GB de RAM do Pi 3
ENV NODE_OPTIONS=--max-old-space-size=512
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
# Pré-comprime os arquivos: o Nginx serve o .gz pronto (gzip_static) e o Pi não gasta CPU comprimindo
RUN npm run build && find dist -type f \( -name '*.js' -o -name '*.css' -o -name '*.html' -o -name '*.svg' \) -exec gzip -9 -k {} +

# Etapa 2: arquivos estáticos servidos pelo Nginx (também atua como proxy da API)
FROM nginx:1.27-alpine
# 1 worker basta para uso doméstico (o padrão "auto" sobe 4 no Pi 3, cada um com sua RAM)
RUN sed -i 's/^worker_processes .*;/worker_processes 1;/' /etc/nginx/nginx.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
