-- Create chats table
CREATE TABLE IF NOT EXISTS chats (
    jid TEXT PRIMARY KEY,
    name TEXT,
    last_message_time TIMESTAMP WITH TIME ZONE,
    last_message TEXT,
    last_sender TEXT,
    last_is_from_me BOOLEAN
);

-- Create messages table
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    sender TEXT NOT NULL,
    content TEXT,
    is_from_me BOOLEAN NOT NULL,
    chat_jid TEXT NOT NULL REFERENCES chats(jid),
    media_type TEXT,
    CONSTRAINT fk_chat
        FOREIGN KEY(chat_jid) 
        REFERENCES chats(jid)
        ON DELETE CASCADE
);

-- Create contacts table
CREATE TABLE IF NOT EXISTS contacts (
    jid TEXT PRIMARY KEY,
    phone_number TEXT NOT NULL,
    name TEXT
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_messages_chat_jid ON messages(chat_jid);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_contacts_phone ON contacts(phone_number);