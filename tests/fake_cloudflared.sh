#!/bin/sh
# cloudflared FALSO para pruebas: imprime una URL trycloudflare y se muere a los FAKE_LIFETIME s.
echo "INF Requesting new quick Tunnel on trycloudflare.com... args: $*"
echo "INF |  https://fake-$(date +%s%N | tail -c 7)-$$.trycloudflare.com  |"
sleep "${FAKE_LIFETIME:-8}"
echo "ERR simulated crash"; exit 1
