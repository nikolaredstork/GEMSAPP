# GEMSAPP

Web aplikacija za editovanje i simulaciju elektroenergetskih sistema zasnovana na Flask backendu i vis-network frontendu. Koristi Antares Modeler kao simulacioni engine.

## Zahtevi

- Python 3.9+
- Antares Modeler binarni fajl (nije uključen u repo)

## Instalacija

### 1. Kloniraj repozitorijum

```bash
git clone git@github.com:nikolaredstork/GEMSAPP.git
cd GEMSAPP
```

### 2. Kreiraj virtuelno okruženje i instaliraj zavisnosti

```bash
python3 -m venv venv
source venv/bin/activate
pip install flask flask-socketio pyyaml
```

### 3. Postavi Antares Modeler

Preuzmi i raspauj Antares binarni paket u root folder projekta tako da putanja bude:

```
GEMSAPP/antares-9.3.2-Ubuntu-22.04/bin/antares-modeler
```

### 4. Pripremi studiju

U root folderu projekta mora postojati bar jedna studija. Struktura studije:

```
MojaStudija/
├── parameters.yml
├── input/
│   ├── system.yml
│   ├── model-libraries/
│   └── data-series/
└── output/
```

Novu studiju možeš kreirati direktno kroz web interfejs.

## Pokretanje

```bash
source venv/bin/activate
python app.py
```

Otvori browser na [http://localhost:5000](http://localhost:5000).

## Upotreba

- **Studije** — kreiraj, učitaj ili obriši studije iz padajućeg menija
- **Editor** — dodaj komponente i konekcije u sistem vizuelno (drag & drop)
- **Biblioteke modela** — uvezi i uređuj YAML biblioteke modela
- **Vremenske serije** — učitaj CSV fajlove sa ulaznim podacima
- **Simulacija** — pokreni Antares Modeler i prati log u realnom vremenu
- **Rezultati** — pregledaj i preuzmi izlazne CSV fajlove
