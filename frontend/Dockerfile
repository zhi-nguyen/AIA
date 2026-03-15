FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package.json package-lock.json ./

# Cài dependencies
RUN npm ci

# Copy source code
COPY . .

# Expose port
EXPOSE 3000

# Chạy Next.js dev server
CMD ["npm", "run", "dev"]
