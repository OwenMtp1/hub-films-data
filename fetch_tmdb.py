#!/usr/bin/env python3
"""Récupère le catalogue films + séries disponibles en streaming en France via l'API TMDB.

Usage :  TMDB_KEY=xxxx python3 fetch_tmdb.py [--films 4000] [--series 1500] [--out ./hub-films-data]
Sortie :
  catalogue.json        un tableau de titres au format du hub (voir README du hub)
  posters/p-NNN.json    les affiches (w154, base64), 50 par fichier, dans l'ordre de popularité
Uniquement la bibliothèque standard Python 3.8+.
Ce produit utilise l'API TMDB mais n'est ni approuvé ni certifié par TMDB.
"""
import argparse, base64, json, math, os, re, sys, time, threading, unicodedata, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

API = "https://api.themoviedb.org/3"
IMG = "https://image.tmdb.org/t/p/w154"
KEY = os.environ.get("TMDB_KEY", "").strip()
if not KEY:
    sys.exit("Définis TMDB_KEY (clé API v3 ou jeton de lecture v4).")
BEARER = len(KEY) > 60  # jeton v4

GENRES = {28: ["Action"], 12: ["Aventure"], 16: ["Animation"], 35: ["Comédie"], 80: ["Policier"], 99: ["Documentaire"],
          18: ["Drame"], 14: ["Fantastique"], 36: ["Historique"], 27: ["Horreur"], 10402: ["Musical"], 9648: ["Thriller"],
          10749: ["Romance"], 878: ["SF"], 53: ["Thriller"], 10752: ["Historique"], 37: ["Aventure"], 10770: [],
          10751: [], 10759: ["Action", "Aventure"], 10765: ["SF", "Fantastique"], 10768: ["Historique", "Drame"]}
EXCLU_TV = {10762, 10763, 10764, 10766, 10767}  # enfants, info, téléréalité, soap, talk-show
PLATS = [("Netflix", ["netflix"]), ("Prime Video", ["amazon prime", "prime video"]), ("Disney+", ["disney"]),
         ("Canal+", ["canal"]), ("Max", ["max", "hbo"]), ("Apple TV+", ["apple tv"]), ("Paramount+", ["paramount"]),
         ("Arte", ["arte"]), ("france.tv", ["france.tv", "france tv", "francetv"])]
KW = {"twist ending": "twist", "plot twist": "twist", "mindfuck": "mind-blowing", "psychological thriller": "psychologie",
      "based on true story": "histoire vraie", "based on a true story": "histoire vraie", "true story": "histoire vraie",
      "biography": "biopic", "war": "guerre", "world war ii": "guerre", "world war i": "guerre", "vietnam war": "guerre",
      "military": "militaire", "heist": "casse", "con artist": "arnaque", "serial killer": "tueurs en série",
      "dystopia": "dystopie", "time travel": "voyage dans le temps", "revenge": "vengeance", "hitman": "tueur à gages",
      "spy": "espionnage", "espionage": "espionnage", "post-apocalyptic future": "post-apo", "superhero": "super-héros",
      "sports": "sport", "car race": "course automobile", "mafia": "mafia", "prison": "prison", "miniseries": "mini-série"}

lock = threading.Lock()
def get(path, **params):
    q = dict(params)
    if not BEARER: q["api_key"] = KEY
    url = f"{API}{path}?{urllib.parse.urlencode(q)}"
    for essai in range(5):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json", **({"Authorization": f"Bearer {KEY}"} if BEARER else {})})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429: time.sleep(2 + essai * 2); continue
            if e.code == 404: return None
            if essai == 4: raise
        except Exception:
            if essai == 4: raise
        time.sleep(1 + essai)

def plat_name(n):
    n = n.lower()
    for nom, keys in PLATS:
        if any(k in n for k in keys) and "channel" not in n: return nom
    return None

def discover(kind, cible):
    ids, page = [], 1
    params = dict(language="fr-FR", watch_region="FR", with_watch_monetization_types="flatrate|free|ads",
                  sort_by="popularity.desc", include_adult="false")
    params["vote_count.gte"] = 30 if kind == "movie" else 15
    while len(ids) < cible and page <= 500:
        d = get(f"/discover/{kind}", page=page, **params)
        if not d or not d.get("results"): break
        for r in d["results"]:
            if kind == "tv" and EXCLU_TV & set(r.get("genre_ids", [])): continue
            ids.append(r["id"])
        page += 1
        if page % 25 == 0: print(f"  {kind}: {len(ids)} ids…", flush=True)
    return ids[:cible]

def detail(kind, i):
    app = "credits,watch/providers,keywords" if kind == "movie" else "watch/providers,keywords"
    d = get(f"/{kind}/{i}", language="fr-FR", append_to_response=app)
    if not d or not d.get("overview"): return None
    fr = (d.get("watch/providers") or {}).get("results", {}).get("FR", {})
    plats = []
    for key in ("flatrate", "free", "ads"):
        for p in fr.get(key, []) or []:
            n = plat_name(p.get("provider_name", ""))
            if n and n not in plats: plats.append(n)
    genres = []
    for g in d.get("genres", []):
        for x in GENRES.get(g["id"], []):
            if x not in genres: genres.append(x)
    kws = (d.get("keywords") or {}).get("keywords" if kind == "movie" else "results", []) or []
    tags = []
    for k in kws:
        t = KW.get(k.get("name", "").lower())
        if t and t not in tags: tags.append(t)
    if any(g["id"] == 10752 for g in d.get("genres", [])) and "guerre" not in tags: tags.append("guerre")
    pays = d.get("origin_country") or [c.get("iso_3166_1") for c in d.get("production_countries", [])]
    if d.get("original_language") == "fr" or "FR" in (pays or [])[:1]: tags.append("français")
    if kind == "tv" and d.get("type") == "Miniseries" and "mini-série" not in tags: tags.append("mini-série")
    if kind == "movie":
        an = (d.get("release_date") or "")[:4]
        rt = d.get("runtime") or 0
        duree = f"{rt // 60} h {rt % 60:02d}" if rt else ""
        real = ", ".join(c["name"] for c in (d.get("credits") or {}).get("crew", []) if c.get("job") == "Director")[:80]
        titre, orig = d.get("title"), d.get("original_title")
    else:
        an = (d.get("first_air_date") or "")[:4]
        n = d.get("number_of_seasons") or 0
        duree = (f"{d.get('number_of_episodes')} épisodes" if d.get("type") == "Miniseries" and d.get("number_of_episodes")
                 else f"{n} saison{'s' if n > 1 else ''}" if n else "")
        real = ", ".join(c["name"] for c in d.get("created_by", []))[:80]
        titre, orig = d.get("name"), d.get("original_name")
    return {"id": f"{'f' if kind == 'movie' else 's'}{i}", "tmdb": i, "titre": titre, "original": orig or "",
            "type": "film" if kind == "movie" else "serie", "annee": int(an) if an.isdigit() else None,
            "genres": genres[:3], "tags": tags[:5], "plateformes": plats[:4], "duree": duree,
            "note": round(d.get("vote_average") or 0, 1) or None, "votes": d.get("vote_count") or 0,
            "pop_raw": d.get("popularity") or 0, "realisateur": real, "description": d.get("overview", "")[:600],
            "poster_path": d.get("poster_path") or ""}

def poster(path):
    if not path: return None
    for essai in range(3):
        try:
            with urllib.request.urlopen(IMG + path, timeout=20) as r:
                return "data:image/jpeg;base64," + base64.b64encode(r.read()).decode()
        except Exception:
            time.sleep(1 + essai)
    return None

def norm(x):
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFD", (x or "").lower()).encode("ascii", "ignore").decode())

def search_extra(e):
    """Titres ajoutés à la main (extras.json) : ceux du hub et ceux qu'Owen a aimés, même hors abonnement."""
    kind = "movie" if e.get("type", "film") == "film" else "tv"
    d = get(f"/search/{kind}", query=e["q"], language="en-US", include_adult="false")
    q, an, res = norm(e["q"]), e.get("annee"), []
    for r in (d or {}).get("results", []):
        noms = [norm(r.get(k)) for k in ("title", "original_title", "name", "original_name")]
        if not any(n and (q in n or n in q) for n in noms): continue
        y = (r.get("release_date") or r.get("first_air_date") or "")[:4]
        if an and (not y.isdigit() or abs(int(y) - an) > 1): continue
        res.append(r)
    res.sort(key=lambda r: r.get("vote_count") or 0, reverse=True)
    return [(kind, r["id"]) for r in res[: e.get("n", 1)]]

def extras(path, deja):
    if not path or not os.path.exists(path): return []
    with open(path, encoding="utf-8") as f: liste = json.load(f)
    with ThreadPoolExecutor(8) as ex: trouves = [x for xs in ex.map(search_extra, liste) for x in xs]
    vus, todo = set(deja), []
    for kind, i in trouves:
        k = f"{'f' if kind == 'movie' else 's'}{i}"
        if k not in vus: vus.add(k); todo.append((kind, i))
    print(f"Extras : {len(trouves)} trouvés, {len(todo)} nouveaux", flush=True)
    with ThreadPoolExecutor(8) as ex: return [r for r in ex.map(lambda x: detail(*x), todo) if r]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--films", type=int, default=4000)
    ap.add_argument("--series", type=int, default=1500)
    ap.add_argument("--out", default="./hub-films-data")
    ap.add_argument("--extras", default="extras.json")
    ap.add_argument("--extras-only", action="store_true", help="ajoute seulement les extras au catalogue existant")
    a = ap.parse_args()
    if a.extras_only: return extras_only(a)
    os.makedirs(os.path.join(a.out, "posters"), exist_ok=True)
    out = []
    for kind, n in (("movie", a.films), ("tv", a.series)):
        print(f"Découverte {kind}…", flush=True)
        ids = discover(kind, n)
        print(f"Détails de {len(ids)} {kind}…", flush=True)
        with ThreadPoolExecutor(8) as ex:
            for k, r in enumerate(ex.map(lambda i: detail(kind, i), ids)):
                if r: out.append(r)
                if k % 250 == 0: print(f"  {k}/{len(ids)}", flush=True)
    out += extras(a.extras, [r["id"] for r in out])
    # popularité 0-100 = rang (films et séries ensemble, pondéré par le nombre de votes)
    out.sort(key=lambda r: r["votes"] * 0.6 + r["pop_raw"] * 40, reverse=True)
    N = len(out)
    for k, r in enumerate(out):
        r["popularite"] = round(99 - 99 * k / max(N - 1, 1))
        r["chunk"] = k // 50
    print(f"Affiches de {N} titres…", flush=True)
    with ThreadPoolExecutor(12) as ex:
        imgs = list(ex.map(lambda r: poster(r["poster_path"]), out))
    chunks = {}
    for r, im in zip(out, imgs):
        r["poster"] = bool(im)
        if im: chunks.setdefault(r["chunk"], {})[r["id"]] = im
        for k in ("poster_path", "pop_raw", "votes"): r.pop(k, None)
    for c, data in chunks.items():
        with open(os.path.join(a.out, "posters", f"p-{c:03d}.json"), "w") as f: json.dump(data, f)
    with open(os.path.join(a.out, "catalogue.json"), "w", encoding="utf-8") as f:
        f.write("[\n" + ",\n".join(json.dumps(r, ensure_ascii=False) for r in out) + "\n]\n")
    print(f"Terminé : {N} titres, {len(chunks)} fichiers d'affiches dans {a.out}", flush=True)

def extras_only(a):
    cat_path = os.path.join(a.out, "catalogue.json")
    with open(cat_path, encoding="utf-8") as f: cat = json.load(f)
    new = extras(a.extras, [r["id"] for r in cat])
    c0 = max([r.get("chunk", 0) for r in cat] + [-1]) + 1
    chunks = {}
    with ThreadPoolExecutor(12) as ex: imgs = list(ex.map(lambda r: poster(r["poster_path"]), new))
    for k, (r, im) in enumerate(zip(new, imgs)):
        r["popularite"] = max(5, min(95, round(25 * math.log10((r["votes"] or 0) + 1))))
        r["chunk"] = c0 + k // 50
        r["poster"] = bool(im)
        if im: chunks.setdefault(r["chunk"], {})[r["id"]] = im
        for x in ("poster_path", "pop_raw", "votes"): r.pop(x, None)
    for c, data in chunks.items():
        with open(os.path.join(a.out, "posters", f"p-{c:03d}.json"), "w") as f: json.dump(data, f)
    cat += new
    with open(cat_path, "w", encoding="utf-8") as f:
        f.write("[\n" + ",\n".join(json.dumps(r, ensure_ascii=False) for r in cat) + "\n]\n")
    print(f"Extras ajoutés : {len(new)} titres, {len(chunks)} fichiers d'affiches", flush=True)

if __name__ == "__main__":
    main()
