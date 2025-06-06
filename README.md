
# 🧠 IntentFlow Curator – Genesys Cloud Intent Curation Tool

Wizard-style web UI that makes it easy to extract, curate, and generate intents and utterances from bot flows in Genesys Cloud.

---

## 🚀 Key Features

- 📥 **YAML flow upload** exported from Architect (Genesys Cloud).
- 🔍 **Automatic extraction** of intents and utterances.
- 🧠 **Duplicate detection** (exact and fuzzy) using RapidFuzz.
- ✍️ **Intent curation** in an editable table (Streamlit `data_editor`).
- 📤 **Excel export** with two sheets: `intents` and `duplicates`.
- 📁 **Upload curated Excel** to generate an updated YAML file.
- 📦 **Generation of the** `settingsNaturalLanguageUnderstanding` **block**.
- 🐳 **Docker-ready** for portable execution.

---

## 🧭 Wizard Flow (4 Simple Steps)

The app guides the user through a 4-step curation wizard:

**Upload YAML**
Import a Genesys Cloud bot flow in YAML format. The app extracts all intents and utterances automatically.

**Review & Curate**
Edit utterances directly in a table and review exact or fuzzy duplicates flagged by the system.

**Generate Updated YAML**
After curation, download the edited intents as a YAML file, ready for Architect. Excel upload is supported for offline collaboration.

**Publish to Genesys (optional)**
Upload the YAML back into Genesys Cloud via Archy CLI by providing your credentials and region.

## 🧱 Project Structure

```bash

auto\_train\_web/
├── app/
│   ├── streamlit\_app.py           # Main app (wizard UI)
│   ├── utils/
│   │   ├── extractor.py           # Extraction & duplicate checking
│   │   └── builder.py             # YAML generation
│   └── auto\_train/
│       ├── loader.py              # Original flow parser
│       └── builder.py             # NLU structure builder
│   └── locales/
│       ├── en.json              # English locale
│       └── es.json              # Spanish locale
             # NLU structure builder
├── Dockerfile
├── requirements.txt
├── .gitignore
├── README.md
└── CHANGELOG.md

````

---

## 🧪 Requirements

- Python 3.10+
- Docker (optional, for containerized execution)

---

## ▶️ Running Locally

```bash
# Create virtual environment
python -m venv .venv
.venv\Scripts\activate    # Windows
# or
source .venv/bin/activate  # Linux/macOS

# Install dependencies
pip install -r requirements.txt

# Launch Streamlit
streamlit run app/streamlit_app.py
````

---

## 🐳 Running with Docker

### Build

```bash
docker build -t auto-train-web .
```

### Run from Local imagen

```bash
docker run -p 8501:8501 auto-train-web
```

### Run from docker hub imagen

```bash
docker run -p 8501:8501 dtobia/auto-train-web:latest
```

### Open in your browser

```bash
http://localhost:8501
```

---

## 📝 License

MIT License © 2025

---

## 📌 Future Roadmap

- [ ] Automatic grouping suggestions with AI (GPT / embeddings).
- [ ] Structure validation for Slots before pushing to Genesys.

