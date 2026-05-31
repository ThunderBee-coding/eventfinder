#!/bin/bash

# Wechsle in das globale Docker-Verzeichnis
cd /docker/eventfinder

echo "Starting EventFinder Stack from /docker/eventfinder..."
docker-compose up --build
