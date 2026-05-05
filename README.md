# ✈️ Travel Advisory

A responsive, client-side web application that provides up-to-date travel safety information, health advisories, and emergency contacts for destinations worldwide.

## Features

- **16 destinations** across Asia, Europe, the Americas, Africa, and Oceania
- **4-tier advisory level system** (Exercise Normal Precautions → Do Not Travel) with colour-coded cards
- **Search** by country name or region
- **Filter** by geographic region and advisory level
- **Click-through detail modal** with:
  - Safety tips
  - Health advisory
  - Emergency numbers (police, ambulance, fire, embassy)
  - Visa and currency information
- Fully **accessible** (keyboard navigable, ARIA roles, screen-reader friendly)
- **Responsive** layout — works on mobile, tablet, and desktop

## Advisory Levels

| Level | Meaning | Colour |
|-------|---------|--------|
| 1 | Exercise Normal Precautions | 🟢 Green |
| 2 | Exercise Increased Caution | 🟡 Yellow |
| 3 | Reconsider Travel | 🟠 Orange |
| 4 | Do Not Travel | 🔴 Red |

## Getting Started

Open `index.html` in any modern browser — no build step or server required.

```
git clone https://github.com/nazi96/Travel-advisory.git
cd Travel-advisory
open index.html   # macOS
# or
start index.html  # Windows
```

## File Structure

```
Travel-advisory/
├── index.html   – Main HTML page
├── styles.css   – Responsive stylesheet
├── data.js      – Advisory data for all destinations
└── script.js    – Search, filter, and modal logic
```

## Disclaimer

Travel advisories are for informational purposes only. Always consult your government's official travel portal before travelling:
- [U.S. State Department](https://travel.state.gov)
- [UK FCDO](https://www.gov.uk/foreign-travel-advice)
- [Smartraveller (Australia)](https://www.smartraveller.gov.au)
