FROM nginx:alpine

# Install openssl for certificate generation
RUN apk add --no-cache openssl

# Copy nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Create SSL directory
RUN mkdir -p /etc/nginx/ssl

# Copy certificate generation script
COPY generate-certs.sh /docker-entrypoint.d/
RUN chmod +x /docker-entrypoint.d/generate-certs.sh

# Expose HTTPS ports
EXPOSE 443 8443 8000

CMD ["nginx", "-g", "daemon off;"]
