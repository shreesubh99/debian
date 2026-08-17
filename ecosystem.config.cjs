module.exports = {
  apps: [
    {
      name: 'ytsk-whatsapp-server',
      script: 'server.js',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '250M',
      env: {
        NODE_ENV: 'production',
        PORT: 3333,
        HOST: '0.0.0.0',
        USE_NGROK: 'true'
      }
    }
  ]
};
