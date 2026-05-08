# ---------------------------------
# Dev Stage: 開発用イメージ
# ---------------------------------
FROM node:20-alpine AS dev
WORKDIR /app
COPY package.json package-lock.json ./

# 開発に必要なツールのインストール
RUN apk add --no-cache curl

RUN npm ci

# ポート公開
EXPOSE 80

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "80"]


# ---------------------------------
# Build Stage: ビルド
# ---------------------------------
FROM node:20-alpine AS builder
WORKDIR /app

# キャッシュを効かせるためにpackage.jsonを先にコピー
COPY package.json package-lock.json ./
# npm install (ci は clean install。再現性を保証)
RUN npm ci

# ソースコードをコピーしてビルド
COPY . .
RUN npm run build

# ---------------------------------
# Production Stage: 本番用イメージ
# ---------------------------------
FROM nginx:alpine AS prod

# Nginxの設定ファイルをコピー
COPY nginx.conf /etc/nginx/conf.d/default.conf

# ビルド成果物をNginxの公開ディレクトリへ配置
# Viteのデフォルト出力先は dist です
COPY --from=builder /app/dist /usr/share/nginx/html

# ポート公開
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]