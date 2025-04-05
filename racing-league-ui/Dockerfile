FROM node:18-alpine as build

# Set working directory
WORKDIR /app

# Copy package files and install dependencies
COPY package*.json ./
RUN npm ci

# Copy source code
COPY . .

# Build the application
RUN npm run build && cp nginx.conf build/

# Debug - list directories to see where build output is located
RUN ls -la

# Production stage
FROM nginx:alpine

# Copy from the build stage using the correct path - adjust based on framework
# Common build directories: dist (Vite), build (CRA), out (Next.js static)
COPY --from=build /app/dist /usr/share/nginx/html
# If dist doesn't work, try:
# COPY --from=build /app/build /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]