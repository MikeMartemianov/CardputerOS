#!/bin/bash
# CardputerOS YouTube Server — Oracle Cloud Free Tier Setup
# Run this on a fresh Ubuntu 24.04 ARM VM from Oracle Cloud

set -e
echo "=== CardputerOS YouTube Server Setup ==="

# 1. Update system
sudo apt-get update && sudo apt-get upgrade -y

# 2. Install dependencies
sudo apt-get install -y python3 python3-pip ffmpeg git

# 3. Install yt-dlp (latest)
sudo curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp
sudo chmod a+rx /usr/local/bin/yt-dlp

# 4. Install Python packages
pip3 install flask

# 5. Clone project
cd /opt
sudo git clone https://github.com/MikeMartemianov/CardputerOS.git
cd CardputerOS/server

# 6. Run OAuth authorization (one-time)
echo ""
echo "=== OAuth Authorization ==="
echo "Run this command and follow the instructions:"
echo "  yt-dlp --username oauth2 --password '' --skip-download https://www.youtube.com/watch?v=dQw4w9WgXcQ"
echo ""
echo "This will show a URL. Open it in browser and authorize."
echo ""

# 7. Create systemd service for auto-start
sudo cat > /etc/systemd/system/cardputeros.service << 'EOF'
[Unit]
Description=CardputerOS YouTube Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/CardputerOS/server
ExecStart=/usr/bin/python3 youtube_proxy.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable cardputeros
echo ""
echo "=== Setup Complete ==="
echo "1. Run OAuth: yt-dlp --username oauth2 --password '' --skip-download https://www.youtube.com/watch?v=dQw4w9WgXcQ"
echo "2. Open the URL in browser and authorize"
echo "3. Start server: sudo systemctl start cardputeros"
echo "4. Your server IP: $(hostname -I | awk '{print $1}'):8080"
echo "5. Set this IP in CardputerOS Settings > YouTube Server"
