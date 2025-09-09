FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

RUN npm ci --only=production && npm cache clean --force

EXPOSE 3000

CMD ["npm", "start"]