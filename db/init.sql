-- Schema for the social-media sentiment analysis pipeline.
-- Created automatically on first postgres container start.

CREATE TABLE IF NOT EXISTS comments (
    id             TEXT PRIMARY KEY,
    source         VARCHAR(32)  NOT NULL,
    author         TEXT,
    text           TEXT         NOT NULL,
    cleaned_text   TEXT,
    label          VARCHAR(16),
    vader_label    VARCHAR(16),
    vader_score    DOUBLE PRECISION,
    vader_positive DOUBLE PRECISION,
    vader_negative DOUBLE PRECISION,
    vader_neutral  DOUBLE PRECISION,
    bert_label     VARCHAR(16),
    bert_score     DOUBLE PRECISION,
    ts             TIMESTAMP,
    post_id        TEXT,
    post_title     TEXT,
    processed_at   TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_comments_ts        ON comments (ts);
CREATE INDEX IF NOT EXISTS idx_comments_source    ON comments (source);
CREATE INDEX IF NOT EXISTS idx_comments_vader     ON comments (vader_label);
CREATE INDEX IF NOT EXISTS idx_comments_post      ON comments (post_id);

-- App accounts (signup / login)
CREATE TABLE IF NOT EXISTS users (
    email          TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    password_hash  TEXT NOT NULL,
    created_at     TIMESTAMP DEFAULT NOW(),
    last_login     TIMESTAMP
);

CREATE TABLE IF NOT EXISTS window_stats (
    window_start  TIMESTAMP NOT NULL,
    window_end    TIMESTAMP NOT NULL,
    total         INTEGER NOT NULL,
    positive      INTEGER NOT NULL,
    negative      INTEGER NOT NULL,
    neutral       INTEGER NOT NULL,
    pos_pct       DOUBLE PRECISION,
    neg_pct       DOUBLE PRECISION,
    neu_pct       DOUBLE PRECISION,
    avg_score     DOUBLE PRECISION,
    top_words     TEXT,
    processed_at  TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (window_start)
);
