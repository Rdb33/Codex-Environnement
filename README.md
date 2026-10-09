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

Le lien change à chaque lancement. Si le téléphone n’arrive pas à ouvrir la page, vérifiez que les deux appareils sont sur le même Wi‑Fi et que le pare-feu autorise le port TCP 8765 sur le réseau local. Certains réseaux invités empêchent les appareils de communiquer entre eux.

## Sécurité et limites

Le serveur écoute sur le réseau local et utilise HTTP. Le code aléatoire protège l’accès à la page, mais le transfert n’est pas chiffré : utilisez un Wi‑Fi de confiance, ne partagez pas le lien et arrêtez le serveur après usage. Les fichiers sont transférés un par un, sans recompression, avec une limite de 1 Gio par fichier. Les fichiers incomplets ne sont pas conservés.
