# hub-films-data

Données du hub « Séries et films » : films et séries disponibles en streaming en France, récupérés via l'API TMDB.

- `fetch_tmdb.py` : le script (Python, bibliothèque standard).
- `.github/workflows/catalogue.yml` : le lance sur les serveurs de GitHub (à la demande, et le 1er de chaque mois).
- `data/catalogue.json` et `data/posters/p-NNN.json` : le résultat.

La clé TMDB est stockée dans le secret de dépôt `TMDB_KEY`, jamais dans le code.

Ce produit utilise l'API TMDB mais n'est ni approuvé ni certifié par TMDB.

## Titres ajoutés à la main (`extras.json`)

Certains titres ne sont sur aucune plateforme d'abonnement en France (location ou achat seulement), donc la découverte TMDB ne les trouve pas.
`extras.json` liste ceux qu'on veut quand même avec leur affiche : les titres choisis dans le hub et les films aimés.
Chaque entrée : `q` (titre anglais ou original), `type` (`film` ou `serie`), `annee` (facultatif, ±1 an), `n` (facultatif, nombre de résultats, pour une saga).
Ils sont ajoutés à chaque lancement mensuel. Pour les ajouter tout de suite sans tout refaire : lancer le workflow à la main avec « extras_only ».
