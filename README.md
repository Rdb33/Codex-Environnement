# Phone Drop

Envoyez plusieurs photos de votre téléphone Android vers un dossier de l’ordinateur, depuis un navigateur et sur le même réseau Wi‑Fi. L’outil utilise uniquement Python standard : aucune dépendance à installer et aucun compte à créer.

## Démarrage sur Arch Linux

Dans un terminal, depuis le dossier du projet :

```sh
python phone_drop.py
```

Choisissez un mot de passe lorsque le programme le demande sur le PC. Le terminal affiche ensuite une adresse locale. Ouvrez-la sur le Poco et saisissez le mot de passe sur la page de connexion. Il est choisi à chaque lancement et n’est pas enregistré sur le disque.

Pour utiliser l’adresse courte `http://phonedrop.local:8765/` sur Arch Linux, installez Avahi une seule fois et démarrez son service :

```sh
sudo pacman -S --needed avahi
sudo systemctl enable --now avahi-daemon
```

Phone Drop publie automatiquement `phonedrop.local` pendant qu’il tourne, sans créer d’entrée DNS inverse susceptible d’entrer en conflit avec le nom du PC. Il affiche l’adresse courte seulement après avoir vérifié qu’elle pointe vers le PC. Si ce nom est déjà utilisé, il essaie `phonedrop-NOM-DU-PC.local` et affiche le nom réellement obtenu. Il retire cette annonce à l’arrêt. Si le nom ne fonctionne pas dans le navigateur du téléphone, utilisez l’adresse IP également affichée. Le téléphone doit prendre en charge les noms `.local`, et le réseau doit laisser passer le trafic mDNS (UDP 5353).

Choisissez des photos dans le sélecteur Android, y compris Google Photos lorsqu’il est proposé. Les aperçus apparaissent avant l’envoi ; la croix sur une photo la retire de la sélection. Vous pouvez en ajouter d’autres avec **Choisir des photos**. Appuyez sur **Envoyer les photos** pour lancer le transfert. Les fichiers reçus pendant cette visite apparaissent dans la liste sous le bouton.

Le dossier par défaut est `~/Pictures/Phone-Imports`. Une fois le transfert fini, faites `Ctrl+C` dans le terminal. Les noms déjà présents sont conservés : un numéro est ajouté au nouveau fichier.

Pour choisir un autre dossier :

```sh
python phone_drop.py --folder ~/Images/Depuis-le-telephone
```

Si plusieurs adresses sont affichées, utilisez celle de l’interface Wi‑Fi (`wlp…` ou `wlan…`) ou Ethernet du réseau local, pas celle d’un VPN ou d’un conteneur.

Si le téléphone indique « adresse indisponible » :

1. Ouvrez la même adresse sur le HP. Si la page ne s’ouvre pas, relancez le serveur et vérifiez que vous copiez `http://`, l’adresse IP et le port `8765`.
2. Vérifiez que le Poco est connecté au Wi‑Fi du HP et que ses données mobiles ou son VPN ne prennent pas le relais. Vérifiez aussi que le Wi‑Fi n’est pas un réseau invité isolant les appareils.
3. Sur le HP, utilisez `ip -4 addr show` pour repérer l’adresse de l’interface Wi‑Fi ou Ethernet. Le lien doit contenir cette adresse.
4. Si le lien fonctionne sur le HP mais pas sur le Poco, vérifiez que le pare-feu du HP autorise les connexions entrantes TCP sur le port `8765` depuis le réseau local.

## Sécurité et limites

Le serveur écoute sur le réseau local et utilise HTTP. Le mot de passe et les photos circulent sans chiffrement : utilisez un Wi‑Fi de confiance et arrêtez le serveur après usage. La connexion reste valable jusqu’à l’arrêt du serveur ; un nouveau mot de passe est demandé au démarrage suivant. Les fichiers sont transférés un par un, sans recompression, avec une limite de 1 Gio par fichier. Les fichiers incomplets ne sont pas conservés.
