#!/bin/bash
# Production Setup Script
# This script helps you create a secure .env.production file

set -e

echo "=================================================="
echo "TaskFlow Production Environment Setup"
echo "=================================================="
echo ""

# Check if .env.production already exists
if [ -f .env.production ]; then
    echo " .env.production already exists!"
    read -p "Do you want to overwrite it? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi
fi

# Copy template
cp .env.production.example .env.production
echo "Created .env.production from template"
echo ""

# Generate SECRET_KEY
echo "Generating SECRET_KEY..."
SECRET_KEY=$(openssl rand -hex 32)
echo "Generated SECRET_KEY"

# Generate PostgreSQL password
echo "Generating PostgreSQL password..."
POSTGRES_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)
echo "Generated PostgreSQL password"

# Generate Redis password
echo "Generating Redis password..."
REDIS_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)
echo "Generated Redis password"

# Update .env.production file
sed -i "s|POSTGRES_PASSWORD=<CHANGE_ME_STRONG_PASSWORD>|POSTGRES_PASSWORD=${POSTGRES_PASSWORD}|g" .env.production
sed -i "s|postgresql://taskflow_prod_user:<CHANGE_ME_STRONG_PASSWORD>@|postgresql://taskflow_prod_user:${POSTGRES_PASSWORD}@|g" .env.production
sed -i "s|SECRET_KEY=<CHANGE_ME_GENERATE_WITH_openssl_rand_hex_32>|SECRET_KEY=${SECRET_KEY}|g" .env.production

# Add Redis password (uncomment and set)
echo "" >> .env.production
echo "# Redis Authentication" >> .env.production
echo "REDIS_PASSWORD=${REDIS_PASSWORD}" >> .env.production

echo ""
echo "=================================================="
echo "Production environment configured successfully!"
echo "=================================================="
echo ""
echo "Your credentials have been saved to .env.production"
echo ""
echo " IMPORTANT SECURITY NOTES:"
echo "   1. NEVER commit .env.production to git"
echo "   2. Store credentials securely (password manager)"
echo "   3. Use different credentials for each environment"
echo "   4. Rotate credentials regularly"
echo ""
echo " Generated credentials:"
echo "   - PostgreSQL Password: ${POSTGRES_PASSWORD}"
echo "   - Redis Password: ${REDIS_PASSWORD}"
echo "   - SECRET_KEY: ${SECRET_KEY:0:20}... (truncated)"
echo ""
echo " Next steps:"
echo "   1. Review .env.production file"
echo "   2. Customize settings if needed"
echo "   3. Deploy with: docker-compose -f docker-compose.prod.yml up -d"
echo ""
echo "See PRODUCTION_DEPLOYMENT.md for full deployment guide"
echo ""
