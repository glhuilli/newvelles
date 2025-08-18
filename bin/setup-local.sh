#!/bin/bash

# Setup script for local development environment

set -e

echo "🚀 Setting up Newvelles local development environment"

# Check if .env.local exists
if [ ! -f ".env.local" ]; then
    echo "📝 Creating .env.local from template..."
    cp env.local.example .env.local
    echo "✅ Created .env.local"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env.local with your actual AWS credentials and test bucket names!"
    echo "   Test buckets should be different from production buckets."
    echo ""
    echo "   Example test bucket names:"
    echo "   - newvelles-test-bucket"
    echo "   - public-newvelles-test-bucket"
    echo ""
else
    echo "✅ .env.local already exists"
fi

# Check if test buckets are configured
echo "🔍 Checking S3 bucket configuration..."
if grep -q "newvelles-test-bucket" .env.local 2>/dev/null; then
    echo "✅ Test S3 buckets configured in .env.local"
else
    echo "⚠️  Please update .env.local with your test S3 bucket names"
fi

echo ""
echo "📋 Next steps:"
echo "1. Edit .env.local with your AWS credentials and test bucket names"
echo "2. Create the test S3 buckets in AWS Console if they don't exist"
echo "3. Run: make test-lambda-docker"
echo ""
echo "🏭 Production vs Testing:"
echo "• Local testing uses buckets from .env.local"
echo "• Production deployment uses buckets from newvelles.ini config"
echo "• This keeps your test data separate from production!"
