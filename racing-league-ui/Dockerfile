FROM node:18-alpine as build

# Set working directory
WORKDIR /app

# Copy package files and install dependencies
COPY package*.json ./
RUN npm ci

# Copy source code
COPY . .

# The API URL is public frontend configuration, supplied at build time.
ARG VITE_API_URL
RUN VITE_API_URL="$VITE_API_URL" npm run build

# Production stage
FROM nginx:alpine

# Copy from the build stage using the correct path - adjust based on framework
# Common build directories: dist (Vite), build (CRA), out (Next.js static)
COPY --from=build /app/dist /usr/share/nginx/html
# If using Create React App (CRA), use this instead:
# COPY --from=build /app/build /usr/share/nginx/html

# Copy custom nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
