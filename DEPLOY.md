# Deployment-Anleitung: n8n Workflow Visualizer auf HuggingFace Spaces

## Voraussetzungen
- HuggingFace Account (Benjamin legt an)
- GitHub Repo: https://github.com/B3NN183/n8n-workflow-visualizer-space

## Schritt-für-Schritt

### 1. HuggingFace Space erstellen
1. Auf https://huggingface.co einloggen
2. → New Space
3. Settings:
   - **Space name:** `n8n-workflow-visualizer`
   - **SDK:** Gradio
   - **Visibility:** Public
   - **Hardware:** CPU Basic (kostenlos für den Start)

### 2. GitHub-Repo verbinden
1. Im Space: Settings → Repository → Link to GitHub Repo
2. Repo auswählen: `B3NN183/n8n-workflow-visualizer-space`
3. Branch: `main`
4. HuggingFace synchronisiert automatisch bei jedem Push

**Alternativ: Direktes Deployment via CLI**
```bash
# HuggingFace CLI installieren
pip install huggingface_hub

# Login (Token unter Settings → Access Tokens anlegen)
huggingface-cli login

# Repo klonen und als HuggingFace Space pushen
git clone https://github.com/B3NN183/n8n-workflow-visualizer-space.git
cd n8n-workflow-visualizer-space
git remote add hf https://huggingface.co/spaces/DEIN_HF_USERNAME/n8n-workflow-visualizer
git push hf main
```

### 3. Space URL nach Deployment
```
https://huggingface.co/spaces/DEIN_HF_USERNAME/n8n-workflow-visualizer
```

### 4. Pricing / API-Key-System

**Empfehlung für MVP:**
- Gumroad oder Stripe: Produkt "n8n Workflow Visualizer — Basic" ($19/Mo) anlegen
- Nach Kauf: API-Key manuell oder via Webhook generieren und per E-Mail senden
- Kunde gibt API-Key im Tool ein → Premium-Features freigeschaltet
- API-Key-Validierung ist aktuell längenbasiert (>8 Zeichen) — bei Bedarf gegen Airtable/DB validierbar

**Upgrade auf echte API-Key-Validierung (optional):**
```python
# In analyze(): statt len(api_key.strip()) > 8
import requests
def validate_key(key: str) -> bool:
    resp = requests.get("https://api.noyra-x.de/validate-key", headers={"X-Key": key})
    return resp.status_code == 200
```

### 5. Lokal testen
```bash
cd n8n-workflow-visualizer-space
pip install -r requirements.txt
python app.py
# → http://localhost:7860
```

## Technische Details

| Aspekt | Detail |
|--------|--------|
| Framework | Gradio 4.44+ |
| Python | 3.9+ |
| Dependencies | networkx, matplotlib, Pillow, numpy |
| Free Features | Node-Statistiken, Typ-Übersicht |
| Premium Features | Graph-Visualisierung, Optimierungstipps, Komplexitäts-Score |
| API-Key-Check | Längencheck >8 Zeichen (MVP) |

## Erweiterungsmöglichkeiten (Post-Launch)
- Echte API-Key-Validierung gegen Airtable
- Pro-Tier: Batch-Upload mehrerer Workflows
- Pro-Tier: PNG-Export der Visualisierung als Download-Button
- Workflow-Vergleich (2 Workflows nebeneinander)
- AI-gestützte Analyse mit Claude API (Workflow-Verbesserungsvorschläge)
