# ♠️ Poker Ranges Trainer

Application Streamlit pour réviser ses ranges d'ouverture 100BB (UTG, UTG1, LJ, HJ, CO, BTN, SB).

- **Entraînement** : une position + une main aléatoire (avec couleurs), tu réponds Fold / Raise / Call, correction immédiate avec la range en surbrillance.
- **Ranges** : consultation de la matrice 13×13 de chaque position et % de combos.
- **Statistiques** : précision par position, mains les plus ratées.
- 4 modes de tirage : uniforme, réaliste (pondéré par combos), mains frontières, focus sur mes erreurs.

## Lancer en local
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Déployer (GitHub → Streamlit Community Cloud)
1. Crée un dépôt GitHub et pousse ce dossier :
   ```bash
   git init && git add . && git commit -m "Poker ranges trainer"
   git branch -M main
   git remote add origin https://github.com/<ton-user>/<ton-repo>.git
   git push -u origin main
   ```
2. Va sur https://share.streamlit.io, connecte ton compte GitHub, clique **New app**.
3. Choisis le dépôt, la branche `main` et le fichier principal `app.py`, puis **Deploy**.

## Mettre à jour les ranges
Modifie l'Excel (mêmes conventions : rouge = raise, vert = call, gris = fold, taille du raise en C17), puis :
```bash
python convert_excel.py range_KT_100BB.xlsx
git add . && git commit -m "Maj ranges" && git push
```
Streamlit Cloud redéploie automatiquement.
