#!/usr/bin/env bash
set -e
SVC="kinga_bot.service"
URL="http://127.0.0.1:5000"
case "$1" in
status) sudo systemctl status "$SVC" --no-pager ;;
logs) sudo journalctl -u "$SVC" -f ;;
buy) curl -s -X POST -H 'Content-Type: application/json' --data '{"action":"buy"}' "$URL/webhook" ;;
sell) curl -s -X POST -H 'Content-Type: application/json' --data '{"action":"sell"}' "$URL/webhook" ;;
reset) rm -f /home/kinga/bot/state.json; sudo systemctl restart "$SVC"; sudo systemctl status "$SVC" --no-pager ;;
*) echo "Użycie: kombajn {status|logs|buy|sell|reset}"; exit 1 ;;
esac
