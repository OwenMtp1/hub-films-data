# hub-films-data

Données du hub « Séries et films » : films et séries disponibles en streaming en France, récupérés via l'API TMDB.

- `fetch_tmdb.py` : le script (Python, bibliothèque standard).
- `.github/workflows/catalogue.yml` : le lance sur les serveurs de GitHub (à la demande, et le 1er de chaque mois).
- `data/catalogue.json` et `data/posters/p-NNN.json` : le résultat.

La clé TMDB est stockée dans le secret de dépôt `TMDB_KEY`, jamais dans le code.

Ce produit utilise l'API TMDB mais n'est ni approuvé ni certifié par TMDB.
