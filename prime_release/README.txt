Meridian 59 Prime - portable folder
===================================

Start (in this folder):
  ./start-server.sh     the game server (game port 5960, admin console port 9999 on this machine only).
                        The FIRST start makes an admin account and prints its password ONCE - write it down.
                        (Choose your own with  M59_ADMIN_PASSWORD=... ./start-server.sh  before the first start.)
  ./start-client.sh     the web client: open the address it prints (default http://127.0.0.1:8080) in a browser.
                        Any account name and password you type at the login screen is created on first login.
  ./stop-all.sh         saves the game and stops the client and the server.
  ./admin.sh "show users"   one admin command on the running server (also: "save game", "show accounts" ...).

Ports in use: game 5960, admin 9999 (set in server/blakserv.cfg; PRIME_ADMIN_PORT for the scripts), gateway 8059 and web 8080 (M59_GATEWAY_PORT, M59_WEB_PORT, and
M59_GAME_PORT if you changed the game port in blakserv.cfg).

Other computers on your network:  M59_WEB_HOST=0.0.0.0 ./start-client.sh   then open http://<this computer's address>:8080
(Do not expose ports 5960 / 9999 to the internet; put a web server with HTTPS in front of port 8080 if you host this publicly.)

Everything lives in this folder: server/ (the game, saves in server/savegame, logs in server/channel and server/console.out),
client/ (web client, game files, gateway), runtime/ (Node.js), tools/ (admin helpers). Nothing is written to your home folder.
Copy the folder anywhere; to keep your world, copy server/savegame along with it.

The server needs a Linux with glibc 2.35 or newer (Ubuntu 22.04 and later, current Arch/Fedora/Debian). On an older system run
./start-server.sh inside the build box:   distrobox enter m59-box -- <this folder>/start-server.sh

Credits and licences: LICENSE (GNU GPL v2) and NOTICE.md. Meridian 59, Server 104 and Meridian Shards are the work of others - thank you.
