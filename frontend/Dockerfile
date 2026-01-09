# Base stage with Node.js 20
FROM node:20-alpine AS base

# Set working directory
WORKDIR /app

# Install dependencies stage
FROM base AS dependencies

# Copy package files
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm install

# Development stage
FROM base AS development

# Copy node_modules from dependencies stage
COPY --from=dependencies /app/node_modules ./node_modules

# Copy application code
COPY . .

# Expose Vite dev server port
EXPOSE 5173

# Development command (will be overridden by docker-compose)
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# Build stage
FROM base AS build

# Copy node_modules from dependencies stage
COPY --from=dependencies /app/node_modules ./node_modules

# Copy application code
COPY . .

# Build application
RUN npm run build

# Production stage
FROM nginx:alpine AS production

# Copy built files from build stage
COPY --from=build /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
