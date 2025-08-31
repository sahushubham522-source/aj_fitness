-- Create table for members
CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT,
    photo TEXT,
    start_date TEXT,
    end_date TEXT
);

-- Create table for fees (multiple per member)
CREATE TABLE IF NOT EXISTS fees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER,
    amount REAL,
    date TEXT,
    FOREIGN KEY (member_id) REFERENCES members(id)
);
