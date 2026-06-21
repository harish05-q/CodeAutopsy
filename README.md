# CodeAutopsy

CodeAutopsy is an AI-assisted reverse-engineering workspace that turns an unfamiliar Python repository into architecture maps, onboarding guidance, risk findings and source-grounded answers.

The repository currently contains the architecture-first product shell: a complete interactive Next.js frontend plus the API, model and implementation specifications for the FastAPI analysis engine.

## Run the frontend

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [API specification](docs/API.md)
- [Data models](docs/DATA_MODELS.md)
- [Development roadmap](docs/ROADMAP.md)

## Palette and interaction direction

The interface deliberately avoids a generic dark AI dashboard. Its visual system uses warm paper, ember red, acid yellow, mint and peach; tactile shadows and editorial typography make the experience feel like a collaborative field notebook. Every major screen is responsive and interactive, including case submission progress, graph inspection, onboarding checklists, repository QA and command navigation.
