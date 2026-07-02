# Local RAG Assistant Promo Site

This is a static promotional website for the Local RAG Assistant project.

It is separate from the Flask + Foundry Local application. This site is safe to deploy on Netlify, GitHub Pages, or any static hosting service.

## Files

```text
local-rag-promo-site/
├── index.html
├── static/
│   ├── styles.css
│   └── script.js
└── README.md
```

## Run Locally

Open `index.html` directly in a browser, or run a simple static server:

```powershell
python -m http.server 8080
```

Then open:

```text
http://127.0.0.1:8080
```

## Deploy

Upload this folder to Netlify or GitHub Pages.

Important: this is only the project introduction website. The real RAG app still needs Python, Flask, SQLite, and Foundry Local, so it runs locally or on a backend server.
