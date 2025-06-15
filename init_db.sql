
CREATE TABLE IF NOT EXISTS utilisateurs (
    id TEXT PRIMARY KEY,
    pseudo TEXT,
    numero_hash TEXT,
    points INTEGER DEFAULT 0,
    accepte_promos BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS programmes_fidelite (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    compagnie TEXT NOT NULL,
    nom_programme TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS evaluations_fidelite (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    programme_id INTEGER,
    user_id TEXT,
    note_accumulation INTEGER,
    note_utilisation INTEGER,
    note_avantages INTEGER,
    commentaire TEXT,
    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (programme_id) REFERENCES programmes_fidelite(id)
);
