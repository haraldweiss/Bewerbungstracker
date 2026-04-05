#!/bin/bash
# Bewerbungstracker Startup-Script für IONOS Shared-Hosting
# Verwendung: bash start-on-ionos.sh

cd /kunden/homepages/22/d956043002/htdocs/clickandbuilds/Wolfinisoftware/Bewerbungstracker

echo "🚀 Starte Bewerbungstracker auf IONOS..."
echo "📱 Die App wird verfügbar unter:"
echo "   → http://82.165.88.152:8080"
echo "   → http://localhost:8080 (via SSH)"
echo ""
echo "⚠️  Diese SSH-Session muss offen bleiben!"
echo "💡 Tipp: Nutze 'screen' oder 'tmux', um die Session zu trennen:"
echo "   screen -S bewerbungstracker"
echo "   bash start-on-ionos.sh"
echo ""

python3 app.py
