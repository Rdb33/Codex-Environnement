# Phone Drop

Envoyez plusieurs photos de votre téléphone Android vers un dossier de l’ordinateur, depuis un navigateur et sur le même réseau Wi‑Fi. L’outil utilise uniquement Python standard : aucune dépendance à installer et aucun compte à créer.

## Démarrage sur Arch Linux

Dans un terminal, depuis le dossier du projet :

```sh
python phone_drop.py
```

Le dossier par défaut est `~/Pictures/Phone-Imports`. Le terminal affiche un lien temporaire contenant un code d’accès. Ouvrez ce lien sur le Poco, choisissez les photos à envoyer, puis appuyez sur **Envoyer**. Une fois le transfert fini, faites `Ctrl+C` dans le terminal. Les noms déjà présents sont conservés : un numéro est ajouté au nouveau fichier.

Pour choisir un autre dossier :

```sh
python phone_drop.py --folder ~/Images/Depuis-le-telephone
```

Le lien change à chaque lancement. Si plusieurs liens sont affichés, utilisez celui de l’interface Wi‑Fi (`wlp…` ou `wlan…`), pas celui d’un VPN, d’un conteneur ou d’une autre interface virtuelle.

Si le téléphone indique « adresse indisponible » :

1. Ouvrez le même lien sur le HP. Si la page ne s’ouvre pas, relancez le serveur et vérifiez que vous copiez le lien complet, avec `http://`, le port `8765` et le code après `?token=`.
2. Vérifiez que le Poco est connecté au Wi‑Fi du HP et que ses données mobiles ou son VPN ne prennent pas le relais. Vérifiez aussi que le Wi‑Fi n’est pas un réseau invité isolant les appareils.
3. Sur le HP, utilisez `ip -4 addr show` pour repérer l’adresse de l’interface Wi‑Fi. Le lien doit contenir cette adresse. Si nécessaire, remplacez seulement l’adresse IP dans le lien affiché, en gardant le port et le code.
4. Si le lien fonctionne sur le HP mais pas sur le Poco, vérifiez que le pare-feu du HP autorise les connexions entrantes TCP sur le port `8765` depuis le réseau local.

## Sécurité et limites

Le serveur écoute sur le réseau local et utilise HTTP. Le code aléatoire protège l’accès à la page, mais le transfert n’est pas chiffré : utilisez un Wi‑Fi de confiance, ne partagez pas le lien et arrêtez le serveur après usage. Les fichiers sont transférés un par un, sans recompression, avec une limite de 1 Gio par fichier. Les fichiers incomplets ne sont pas conservés.
