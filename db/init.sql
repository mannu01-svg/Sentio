-- Schema for the social-media sentiment analysis pipeline.
-- Created automatically on first postgres container start.

CREATE TABLE IF NOT EXISTS comments (
    id             TEXT PRIMARY KEY,
    source         VARCHAR(32)  NOT NULL,
    author         TEXT,
    text           TEXT         NOT NULL,
    cleaned_text   TEXT,
    label          TEXT,
    vader_label    TEXT,
    vader_score    DOUBLE PRECISION,
    vader_positive DOUBLE PRECISION,
    vader_negative DOUBLE PRECISION,
    vader_neutral  DOUBLE PRECISION,
    bert_label     TEXT,
    bert_score     DOUBLE PRECISION,
    llm_label      TEXT,
    llm_score      DOUBLE PRECISION,
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

-- every analysis the user runs (link / account / keyword / topic / paste)
-- so all history is preserved and viewable later, even across API restarts
CREATE TABLE IF NOT EXISTS history (
    id            SERIAL PRIMARY KEY,
    kind          TEXT NOT NULL,             -- post | account | topic | keyword
    post_id       TEXT,                      -- topic post id / single post id
    title         TEXT,                      -- human label of what was analyzed
    platform      TEXT,                      -- youtube | reddit | x | instagram | facebook | threads | paste
    handle        TEXT,                      -- account handle (account analyses)
    keyword       TEXT,                      -- keyword / topic searched
    posts         TEXT,                      -- comma-separated post ids belonging to this analysis
    comments_published INTEGER DEFAULT 0,
    created_at    TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_history_created ON history (created_at DESC);

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
