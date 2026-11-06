#!/usr/bin/env bash
# =============================================================================
# Oracle Cloud (Ubuntu VM) par IPO backend deploy karne ka script.
#
# Kaise chalana hai (VM par SSH karke, is repo ke folder me):
#     DOMAIN=apna-naam.duckdns.org bash deploy_oracle.sh
#
# DOMAIN kyun: app HTTPS maangta hai (Android release build seedha http:// ko block
# karta hai). Free domain: duckdns.org par ek naam banao aur usse VM ke public IP par
# point karo. Caddy us domain ka free HTTPS certificate khud le leta hai.
#
# Oracle console me bhi (ek baar): VCN -> Security List -> Ingress Rules me
# TCP port 80 aur 443 (source 0.0.0.0/0) allow karo. Bina iske bahar se site nahi khulegi.
#
# NOTE: ye script maine Oracle VM par test nahi kiya hai (yahan se access nahi) —
# standard Ubuntu + Docker steps hain. Koi step fail ho toh error text bhej dena.
# =============================================================================
set -euo pipefail

if [ -z "${DOMAIN:-}" ]; then
  echo "DOMAIN set nahi hai. Aise chalao:  DOMAIN=apna-naam.duckdns.org bash deploy_oracle.sh"
  exit 1
fi

cd "$(dirname "$0")"

echo ">> Docker install"
sudo apt-get update
sudo apt-get install -y docker.io iptables-persistent
sudo systemctl enable --now docker

echo ">> VM ka firewall: port 80/443 kholo (Oracle Ubuntu images me default band hota hai)"
sudo iptables -C INPUT -p tcp --dport 80  -j ACCEPT 2>/dev/null || sudo iptables -I INPUT 5 -p tcp --dport 80  -j ACCEPT
sudo iptables -C INPUT -p tcp --dport 443 -j ACCEPT 2>/dev/null || sudo iptables -I INPUT 5 -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save

echo ">> Backend image build (pehli baar 5-10 min lag sakte hain: Chromium download hota hai)"
sudo docker build -t ipo-backend .

sudo docker network create ipo-net 2>/dev/null || true

echo ">> Backend container start"
sudo docker rm -f ipo-backend 2>/dev/null || true
sudo docker run -d --name ipo-backend --restart unless-stopped \
  --network ipo-net -e PORT=10000 -v ipo-data:/data ipo-backend

echo ">> HTTPS reverse proxy (Caddy) start: https://$DOMAIN"
sudo docker rm -f ipo-caddy 2>/dev/null || true
sudo docker run -d --name ipo-caddy --restart unless-stopped \
  --network ipo-net -p 80:80 -p 443:443 -v caddy-data:/data \
  caddy:2 caddy reverse-proxy --from "$DOMAIN" --to ipo-backend:10000

echo
echo "Ho gaya. 1-2 min baad browser me kholo:  https://$DOMAIN/"
echo "Phir app/App.js me BASE_URL ko  'https://$DOMAIN'  se badal ke naya app build karo."
echo "Logs dekhne ke liye:  sudo docker logs -f ipo-backend"
