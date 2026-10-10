#!/usr/bin/env python3
"""Receive files from a phone on the same Wi-Fi network."""

from __future__ import annotations

import argparse
import getpass
import html
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

MAX_FILE_SIZE = 1024 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024
COOKIE_NAME = "phone_drop_session"

STYLE = """
*{box-sizing:border-box}
body{font:16px system-ui,sans-serif;background:#f3f5f8;color:#172033;margin:0;padding:24px}
main{max-width:720px;margin:5vh auto;background:white;padding:28px;border-radius:20px;box-shadow:0 8px 32px #17203312}
h1{margin:0 0 8px}h2{font-size:18px;margin-top:30px}p{color:#596579;line-height:1.5}
button,.pick{display:inline-block;border:0;border-radius:12px;padding:14px 18px;background:#2458d3;color:white;font:inherit;font-weight:650;cursor:pointer}
button:disabled{opacity:.5;cursor:default}.pick{width:100%;text-align:center}
input[type=file]{display:none}
input[type=password]{display:block;width:100%;font:inherit;padding:14px;border:1px solid #aab3c2;border-radius:10px;margin:16px 0}
#send{width:100%;margin-top:16px;background:#172033}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(125px,1fr));gap:12px;margin-top:16px}
.card{position:relative;border:1px solid #dce1e9;border-radius:12px;overflow:hidden;background:#f8f9fb}
.card img{display:block;width:100%;height:112px;object-fit:cover}
.card span{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;padding:8px;font-size:12px}
.remove{position:absolute;right:6px;top:6px;background:#172033dc;border-radius:50%;width:30px;height:30px;padding:0;font-size:21px;line-height:1}
#status{white-space:pre-wrap;min-height:24px;margin-top:16px}#received{padding-left:20px;overflow-wrap:anywhere}
.error{color:#b42318}small{color:#69758a}
"""

# Keep JavaScript in a raw string: Python must not turn "\n" into a line break
# inside a JavaScript string literal.
UPLOAD_SCRIPT = r"""
const picker = document.querySelector('#files');
const previews = document.querySelector('#previews');
const selection = document.querySelector('#selection');
const send = document.querySelector('#send');
const status = document.querySelector('#status');
const received = document.querySelector('#received');
const selected = new Map();
let nextId = 0;
let busy = false;

function render() {
  previews.replaceChildren();
  for (const [id, item] of selected) {
    const card = document.createElement('div');
    card.className = 'card';
    const image = document.createElement('img');
    image.src = item.url;
    image.alt = item.file.name;
    const name = document.createElement('span');
    name.textContent = item.file.name;
    const remove = document.createElement('button');
    remove.className = 'remove';
    remove.type = 'button';
    remove.textContent = '×';
    remove.setAttribute('aria-label', 'Retirer ' + item.file.name);
    remove.disabled = busy;
    remove.onclick = () => {
      URL.revokeObjectURL(item.url);
      selected.delete(id);
      render();
    };
    card.append(image, name, remove);
    previews.append(card);
  }
  selection.textContent = selected.size
    ? selected.size + ' photo(s) à envoyer'
    : 'Aucune photo sélectionnée';
  send.disabled = busy || selected.size === 0;
  picker.disabled = busy;
}

picker.onchange = () => {
  for (const file of picker.files) {
    const id = nextId++;
    selected.set(id, {file, url: URL.createObjectURL(file)});
  }
  picker.value = '';
  status.textContent = '';
  render();
};

send.onclick = async () => {
  busy = true;
  render();
  let done = 0;
  for (const [id, item] of [...selected]) {
    const file = item.file;
    status.textContent = 'Envoi de ' + file.name + '…';
    try {
      const response = await fetch('/upload?name=' + encodeURIComponent(file.name), {
        method: 'POST',
        headers: {'X-Phone-Drop': 'upload', 'Content-Type': 'application/octet-stream'},
        body: file
      });
      if (!response.ok) throw Error(await response.text());
      const entry = document.createElement('li');
      entry.textContent = file.name;
      received.prepend(entry);
      URL.revokeObjectURL(item.url);
      selected.delete(id);
      done++;
    } catch (error) {
      status.textContent = 'Échec pour ' + file.name + ' : ' + error.message
        + '\n' + done + ' fichier(s) reçu(s).';
      break;
    }
  }
  if (selected.size === 0) {
    status.textContent = 'Terminé : ' + done + ' fichier(s) reçu(s).';
  }
  busy = false;
  render();
};

render();
"""


def page(title: str, content: str, script: str = "") -> bytes:
    return (
        '<!doctype html><html lang="fr"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{html.escape(title)}</title><style>{STYLE}</style>'
        f'<main>{content}</main><script>{script}</script></html>'
    ).encode("utf-8")


def login_page(error: bool = False) -> bytes:
    message = '<p class="error">Mot de passe incorrect.</p>' if error else ""
    return page(
        "Connexion · Phone Drop",
        '<h1>Phone Drop</h1><p>Entrez le mot de passe choisi sur l’ordinateur '
        'pour envoyer des photos.</p>'
        f'{message}<form method="post" action="/login">'
        '<label for="password">Mot de passe</label>'
        '<input id="password" name="password" type="password" required autofocus>'
        '<button type="submit">Se connecter</button></form>',
    )


def upload_page(folder: Path) -> bytes:
    content = (
        '<h1>Envoyer des photos</h1><p>Destination : '
        f'<b>{html.escape(str(folder))}</b></p>'
        '<label class="pick" for="files">Choisir des photos</label>'
        '<input id="files" type="file" accept="image/*" multiple>'
        '<p id="selection">Aucune photo sélectionnée</p>'
        '<div class="grid" id="previews"></div>'
        '<button id="send" disabled>Envoyer les photos</button>'
        '<div id="status" role="status"></div>'
        '<h2>Fichiers reçus pendant cette visite</h2><ul id="received"></ul>'
        '<small>Gardez cette page ouverte jusqu’à la fin du transfert.</small>'
    )
    return page("Envoyer des photos · Phone Drop", content, UPLOAD_SCRIPT)


def route_address() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("192.0.2.1", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def local_addresses() -> list[tuple[str, str]]:
    """List active IPv4 interfaces, with Wi-Fi first on Linux."""
    try:
        result = subprocess.run(
            ["ip", "-j", "-4", "addr", "show", "up"],
            check=True, capture_output=True, text=True,
        )
        interfaces = json.loads(result.stdout)
        addresses = [
            (interface["ifname"], address["local"])
            for interface in interfaces
            for address in interface.get("addr_info", [])
            if address.get("scope") == "global" and address.get("family") == "inet"
        ]
        if addresses:
            return sorted(addresses, key=lambda item: (not item[0].startswith("wl"), item[0]))
    except (OSError, subprocess.CalledProcessError, ValueError, KeyError):
        pass
    return [("adresse détectée", route_address())]


def publish_local_name(address: str) -> tuple[subprocess.Popen[bytes], str] | None:
    """Publish an available temporary mDNS alias through Avahi."""
    if not shutil.which("avahi-publish") or not shutil.which("avahi-resolve-host-name"):
        return None
    computer = re.sub(r"[^a-z0-9-]", "-", socket.gethostname().split(".")[0].lower())
    names = ["phonedrop.local", f"phonedrop-{computer or 'pc'}.local"]
    for name in names:
        try:
            process = subprocess.Popen(
                ["avahi-publish", "-a", "-R", name, address],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except OSError:
            return None
        for _ in range(12):
            if process.poll() is not None:
                break
            try:
                result = subprocess.run(
                    ["avahi-resolve-host-name", "-4", name],
                    capture_output=True, text=True, timeout=1,
                )
                if result.returncode == 0 and result.stdout.split()[-1:] == [address]:
                    return process, name
            except (OSError, subprocess.TimeoutExpired):
                pass
            time.sleep(0.25)
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    return None


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


def make_handler(folder: Path, password: str, session: str):
    class Handler(BaseHTTPRequestHandler):
        server_version = "PhoneDrop/2.0"

        def log_message(self, _format: str, *_args: object) -> None:
            return

        def send_content(self, status: int, data: bytes, content_type: str,
                         extra_headers: dict[str, str] | None = None) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            for key, value in (extra_headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(data)

        def send_text(self, status: int, message: str) -> None:
            self.send_content(status, message.encode(), "text/plain; charset=utf-8")

        def authenticated(self) -> bool:
            try:
                jar = cookies.SimpleCookie()
                jar.load(self.headers.get("Cookie", ""))
                item = jar.get(COOKIE_NAME)
                return item is not None and secrets.compare_digest(item.value, session)
            except cookies.CookieError:
                return False

        def do_GET(self) -> None:
            if urlsplit(self.path).path != "/":
                self.send_text(404, "Adresse inconnue.")
                return
            data = upload_page(folder) if self.authenticated() else login_page()
            self.send_content(200, data, "text/html; charset=utf-8")

        def do_POST(self) -> None:
            path = urlsplit(self.path).path
            if path == "/login":
                self.login()
            elif path == "/upload":
                self.upload()
            else:
                self.send_text(404, "Adresse inconnue.")

        def login(self) -> None:
            try:
                size = int(self.headers.get("Content-Length", "-1"))
            except ValueError:
                size = -1
            if size < 0 or size > 4096:
                self.send_text(400, "Formulaire invalide.")
                return
            form = parse_qs(self.rfile.read(size).decode("utf-8", errors="replace"))
            attempted = form.get("password", [""])[0]
            if not secrets.compare_digest(attempted, password):
                self.send_content(403, login_page(error=True), "text/html; charset=utf-8")
                return
            self.send_content(
                303, b"", "text/plain; charset=utf-8",
                {"Location": "/", "Set-Cookie": (
                    f"{COOKIE_NAME}={session}; HttpOnly; SameSite=Strict; Path=/"
                )},
            )

        def upload(self) -> None:
            if not self.authenticated() or self.headers.get("X-Phone-Drop") != "upload":
                self.send_text(403, "Connectez-vous d’abord.")
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
            name = safe_filename(query.get("name", ["photo"])[0])
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
    password = getpass.getpass("Choisissez un mot de passe (8 caractères minimum) : ")
    if len(password) < 8:
        sys.exit("Le mot de passe doit contenir au moins 8 caractères.")
    if password != getpass.getpass("Confirmez le mot de passe : "):
        sys.exit("Les mots de passe ne correspondent pas.")
    folder = args.folder.expanduser().resolve()
    folder.mkdir(parents=True, exist_ok=True)
    session = secrets.token_urlsafe(32)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(folder, password, session))
    server.daemon_threads = True
    server.save_lock = threading.Lock()
    print(f"Dossier : {folder}", flush=True)
    addresses = local_addresses() if args.host == "0.0.0.0" else [("interface choisie", args.host)]
    local_ip = next(
        (ip for interface, ip in addresses if interface.startswith(("wl", "en", "eth"))),
        None,
    )
    if args.host not in ("0.0.0.0", "127.0.0.1"):
        local_ip = args.host
    published = publish_local_name(local_ip) if local_ip else None
    print("Ouvrez cette adresse depuis un autre appareil sur le même réseau :", flush=True)
    if published:
        print(f"  http://{published[1]}:{server.server_port}/", flush=True)
    for interface, ip in addresses:
        print(f"  {interface}: http://{ip}:{server.server_port}/", flush=True)
    if not published:
        print("Nom local indisponible : vérifiez Avahi ou un conflit de nom.", flush=True)
    print("Utilisez l’adresse de l’interface Wi-Fi ou Ethernet du réseau local.", flush=True)
    print("Arrêter le serveur : Ctrl+C. Réseau local uniquement.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServeur arrêté.")
    finally:
        server.server_close()
        if published and published[0].poll() is None:
            published[0].terminate()
            try:
                published[0].wait(timeout=2)
            except subprocess.TimeoutExpired:
                published[0].kill()
                published[0].wait()


if __name__ == "__main__":
    main()
