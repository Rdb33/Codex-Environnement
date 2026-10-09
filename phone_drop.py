#!/usr/bin/env python3
"""Receive files from a phone on the same Wi-Fi network."""

from __future__ import annotations

import argparse
import html
import os
import secrets
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlsplit

MAX_FILE_SIZE = 1024 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024


def lan_address() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("192.0.2.1", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def safe_filename(name: str) -> str:
    # Treat both Unix and Windows separators as path separators.
    name = name.replace("\\", "/").split("/")[-1].strip().strip(".")
    name = "".join(c for c in name if c.isprintable() and c not in "\x00")
    return name[:240] or "photo"


def available_path(folder: Path, name: str) -> Path:
    path = folder / name
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    index = 1
    while True:
        candidate = folder / f"{stem}_{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def make_handler(folder: Path, token: str):
    class Handler(BaseHTTPRequestHandler):
        server_version = "PhoneDrop/1.0"

        def log_message(self, _format: str, *_args: object) -> None:
            # Request URLs contain the access token; never log them.
            return

        def send_text(self, status: int, message: str) -> None:
            data = message.encode()
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def authorized(self) -> bool:
            return secrets.compare_digest(self.headers.get("X-Transfer-Token", ""), token)

        def do_GET(self) -> None:
            query = parse_qs(urlsplit(self.path).query)
            if not secrets.compare_digest(query.get("token", [""])[0], token):
                self.send_text(403, "Code d’accès incorrect. Ouvrez le lien affiché sur l’ordinateur.")
                return
            page = f"""<!doctype html>
<html lang="fr"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta charset="utf-8"><title>Phone Drop</title>
<style>
*{{box-sizing:border-box}}body{{font:16px system-ui,sans-serif;background:#f3f5f8;color:#172033;margin:0;padding:24px}}
main{{max-width:520px;margin:8vh auto;background:white;padding:28px;border-radius:20px;box-shadow:0 8px 32px #17203312}}
h1{{margin:0 0 8px}}p{{color:#596579}}button,label.pick{{display:block;width:100%;border:0;border-radius:12px;padding:15px;background:#2458d3;color:white;font-size:17px;font-weight:650;text-align:center;cursor:pointer}}
input{{display:none}}#send{{margin-top:12px;background:#172033}}#status{{white-space:pre-wrap;min-height:24px;margin-top:16px}}small{{color:#69758a}}
</style><main><h1>Envoyer des photos</h1><p>Choisissez une ou plusieurs photos. Elles seront copiées dans <b>{html.escape(str(folder))}</b>.</p>
<label class="pick" for="files">Choisir des photos</label><input id="files" type="file" accept="image/*" multiple>
<p id="selection"><small>Aucun fichier choisi</small></p><button id="send" disabled>Envoyer</button><div id="status" role="status"></div>
<small>Gardez cette page ouverte jusqu’à la fin du transfert.</small></main>
<script>
const token={token!r}, files=document.querySelector('#files'), send=document.querySelector('#send'), status=document.querySelector('#status');
files.onchange=()=>{{document.querySelector('#selection').textContent=files.files.length?files.files.length+' fichier(s) sélectionné(s)':'Aucun fichier choisi';send.disabled=!files.files.length;status.textContent=''}};
send.onclick=async()=>{{send.disabled=true;let done=0;for(const f of files.files){{status.textContent='Envoi de '+f.name+' ('+(done+1)+'/'+files.files.length+')…';try{{const r=await fetch('/upload?name='+encodeURIComponent(f.name),{{method:'POST',headers:{{'X-Transfer-Token':token,'Content-Type':'application/octet-stream'}},body:f}});if(!r.ok)throw Error(await r.text());done++;status.textContent='Envoyé : '+f.name+' ('+done+'/'+files.files.length+')'}}catch(e){{status.textContent='Échec pour '+f.name+' : '+e.message+'\n'+done+' fichier(s) envoyé(s).';send.disabled=false;return}}}}status.textContent='Terminé : '+done+' fichier(s) reçu(s).';files.value='';document.querySelector('#selection').textContent='Aucun fichier choisi'}};
</script></html>""".encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(page)

        def do_POST(self) -> None:
            if not self.authorized():
                self.send_text(403, "Code d’accès incorrect.")
                return
            if urlsplit(self.path).path != "/upload":
                self.send_text(404, "Adresse inconnue.")
                return
            try:
                size = int(self.headers.get("Content-Length", "-1"))
            except ValueError:
                size = -1
            if size < 0:
                self.send_text(411, "Taille du fichier manquante.")
                return
            if size > MAX_FILE_SIZE:
                self.send_text(413, "Fichier trop volumineux (limite : 1 Gio).")
                return
            query = parse_qs(urlsplit(self.path).query)
            name = safe_filename(unquote(query.get("name", ["photo"])[0]))
            temp = folder / f".{secrets.token_hex(12)}.part"
            remaining = size
            try:
                with temp.open("xb") as output:
                    while remaining:
                        chunk = self.rfile.read(min(CHUNK_SIZE, remaining))
                        if not chunk:
                            raise ConnectionError("transfert interrompu")
                        output.write(chunk)
                        remaining -= len(chunk)
                with self.server.save_lock:
                    destination = available_path(folder, name)
                    os.replace(temp, destination)
            except (OSError, ConnectionError) as error:
                temp.unlink(missing_ok=True)
                self.send_text(500, f"Impossible d’enregistrer le fichier : {error}")
                return
            self.send_text(201, f"Reçu : {destination.name}")

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", type=Path, default=Path.home() / "Pictures" / "Phone-Imports",
                        help="dossier de destination (défaut : ~/Pictures/Phone-Imports)")
    parser.add_argument("--host", default="0.0.0.0", help="interface d’écoute (défaut : toutes les interfaces)")
    parser.add_argument("--port", type=int, default=8765, help="port HTTP (défaut : 8765)")
    args = parser.parse_args()
    folder = args.folder.expanduser().resolve()
    folder.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(9)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(folder, token))
    server.daemon_threads = True
    server.save_lock = threading.Lock()
    ip = lan_address() if args.host == "0.0.0.0" else args.host
    print(f"Dossier : {folder}", flush=True)
    print(f"Sur le téléphone : http://{ip}:{server.server_port}/?token={quote(token)}", flush=True)
    print("Arrêter le serveur : Ctrl+C. Réseau local uniquement.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServeur arrêté.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
