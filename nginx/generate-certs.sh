#!/bin/sh
# Generate self-signed SSL certificate if not exists

SSL_DIR="/etc/nginx/ssl"
CERT_FILE="$SSL_DIR/server.crt"
KEY_FILE="$SSL_DIR/server.key"

if [ ! -f "$CERT_FILE" ] || [ ! -f "$KEY_FILE" ]; then
    echo "Generating self-signed SSL certificate..."
    
    # Check if certificates exist in /opt/KrotPN/ssl (mounted volume)
    if [ -f "/opt/krotpn/ssl/server.crt" ] && [ -f "/opt/krotpn/ssl/server.key" ]; then
        echo "Using existing certificates from /opt/krotpn/ssl"
        cp /opt/krotpn/ssl/server.crt "$CERT_FILE"
        cp /opt/krotpn/ssl/server.key "$KEY_FILE"
    else
        echo "Creating new self-signed certificate..."
        openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
            -keyout "$KEY_FILE" \
            -out "$CERT_FILE" \
            -subj "/C=RU/ST=Moscow/L=Moscow/O=KrotPN/OU=IT/CN=krotpn.local"
        
        # Save to mounted volume for persistence
        mkdir -p /opt/krotpn/ssl
        cp "$CERT_FILE" /opt/krotpn/ssl/
        cp "$KEY_FILE" /opt/krotpn/ssl/
        
        echo "Certificate generated and saved to /opt/krotpn/ssl"
    fi
fi

echo "SSL certificates ready"
