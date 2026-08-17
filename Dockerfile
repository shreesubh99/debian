# Use official Node.js LTS image
FROM node:20-slim

# Install system dependencies for Puppeteer & Chrome
USER root
RUN apt-get update && apt-get install -y \
    git \
    wget \
    gnupg \
    ca-certificates \
    procps \
    libxss1 \
    libgbm1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    fonts-ipafont-gothic \
    fonts-wqy-zenhei \
    fonts-thai-tlwg \
    fonts-kacst \
    fonts-freefont-ttf \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Set up working directory and grant permissions to default 'node' user
WORKDIR /app

# Copy dependency configs
COPY package*.json ./

# Install dependencies (Skip browser download inside npm install to prevent failures)
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
RUN npm install

# Install Chrome browser via Puppeteer CLI
ENV PUPPETEER_CACHE_DIR=/app/.puppeteer_cache
RUN npx puppeteer browsers install chrome@146.0.7680.31

# Copy app source code
COPY . .

# Set permissions for node user (Hugging Face security requirement)
RUN chown -R node:node /app

# Switch to non-privileged user
USER node

# Hugging Face Spaces expects the app to listen on port 7860
ENV PORT=7860
ENV HOST=0.0.0.0
EXPOSE 7860

# Start command
CMD ["node", "--max-old-space-size=200", "server.js"]
