#!/bin/bash
# Script to finalize debian package setup

cd /home/dhruv/TaskFlow

# Create source directory
mkdir -p debian/source

# Create source format file
echo "3.0 (native)" > debian/source/format

# Make rules and scripts executable
chmod +x debian/rules
chmod +x debian/postinst
chmod +x debian/prerm
chmod +x debian/postrm

echo "Debian package structure created successfully!"

