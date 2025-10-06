
# ProFootGn – Backend Django + DRF (MySQL)

Backend prêt à l’emploi pour FootGnPro (LiveScore guinéen).  
Frontend recommandé : React/Vite (non inclus ici).

## 🚀 Démarrage rapide

1) **Créer et activer** un environnement virtuel (Windows PowerShell) :
```ps1
python -m venv env
env\Scripts\activate
```

2) **Installer les dépendances** :
```bash
pip install -r requirements.txt
```

3) **Configurer la base MySQL** : crée une base, puis dans `.env` ou variables système :
```
DB_NAME=profootgn
DB_USER=root
DB_PASSWORD=your_password
DB_HOST=127.0.0.1
DB_PORT=3306
DEBUG=True
ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

4) **Migrations** :
```bash
python manage.py makemigrations
python manage.py migrate
```

5) **Superuser** :
```bash
python manage.py createsuperuser
```

6) **Lancer le serveur** :
```bash
python manage.py runserver
```

7) **Media (logos/photos)**  
Les fichiers uploadés vont dans `media/`. En dev : Django sert ces fichiers.

## 🌐 Endpoints principaux

- `GET /api/matches/` – liste des matchs (filtrage par `status`, `date_from`, `date_to`)
- `GET /api/rounds/` – journées (rounds)
- `GET /api/standings/` – classement calculé
- `GET /api/top-scorers/` – classement des buteurs
- `GET /api/clubs/` – clubs avec logos
- `GET /api/clubs/{id}/` – détail club (+ joueurs)
- CRUD généraux via ViewSets : clubs, players, matches, rounds, goals, cards, news, scoutings

## 🧩 Apps incluses

- `clubs` – clubs/équipes
- `players` – joueurs
- `matches` – matchs, buts, cartons, journées (rounds)
- `stats` – endpoints calculés (classement, buteurs)
- `news` – actualités
- `recruitment` – mise en relation joueurs/recruteurs (simple)
- `users` – profil utilisateur léger (facultatif).

> Auth avancée (JWT) non incluse par défaut pour garder simple. À ajouter plus tard (djangorestframework-simplejwt) si besoin.

## 📦 Versions conseillées
- Python 3.11+
- MySQL 8.x (ou MariaDB récent)

Bon build !


---
## 🔐 Auth JWT (optionnelle)
Endpoints :
- `POST /api/auth/token/` (username, password) → access & refresh
- `POST /api/auth/token/refresh/` (refresh)

Ajoute des permissions DRF au besoin sur tes ViewSets.

## 🧪 Données de démo
Charge tout d’un coup :
```bash
python manage.py load_demo_data
```
Tu auras :
- Clubs : Hafia FC, AS Kaloum
- Joueurs : 2 exemples
- Journée 1 + 1 match fini + 1 but

## 🐳 Docker (dev)
```bash
docker compose up --build
```
Backend sur `http://localhost:8000` — MySQL accessible sur `localhost:3306` (user=root, pass=root).
