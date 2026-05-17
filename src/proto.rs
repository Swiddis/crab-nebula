use std::{iter, str, string};
use thiserror::Error;

#[derive(Debug, Clone)]
#[allow(unused)]
pub struct User {
    pub id: usize,
    pub team: usize,
    pub name: String,
    pub color: String,
}

#[derive(Debug, Clone)]
#[allow(unused)]
pub struct Planet {
    pub id: usize,
    pub owner: usize,
    pub ships: f64,
    pub x: f64,
    pub y: f64,
    pub production: f64,
    pub radius: f64,
}

#[derive(Debug, Clone)]
#[allow(unused)]
pub struct Fleet {
    pub id: usize,
    pub owner: usize,
    pub source: usize,
    pub target: usize,
    pub ships: f64,
    pub x: f64,
    pub y: f64,
    pub radius: f64,
}

#[derive(Debug, Clone)]
pub struct SyncEntity {
    pub id: usize,
    pub x: Option<f64>,
    pub y: Option<f64>,
    pub ships: Option<f64>,
    pub radius: Option<f64>,
    pub owner: Option<usize>,
    pub target: Option<usize>,
}

#[derive(Debug, Clone)]
#[allow(unused)]
pub enum SetMeta {
    You(usize),
    Speed(f64),
    State(String),
}

#[derive(Debug, Clone)]
#[allow(unused)]
pub enum ServerMessage {
    Set(SetMeta),
    Reset,
    User(User),
    Planet(Planet),
    Fleet(Fleet),
    Cancel(usize),
    Sync(Vec<SyncEntity>),
    Destroy(usize),
    Tick(f64),
    Results(Vec<String>),
    Pong(String),
    Print(String),
    Err(String),
}

#[derive(Debug, Clone)]
#[allow(unused)]
pub enum ClientMessage {
    Login {
        name: String,
        token: String,
    },
    Send {
        proportion: f64,
        source: usize,
        target: usize,
    },
    Redir {
        source: usize,
        target: usize,
    },
    Surrender,
    Tock,
    Ping(String),
    Message(String),
}

impl string::ToString for ClientMessage {
    fn to_string(&self) -> String {
        match self {
            ClientMessage::Login { name, token } => format!("/LOGIN\t{}\t{}", name, token),
            ClientMessage::Send {
                proportion,
                source,
                target,
            } => {
                let pct = (proportion * 100.0).round().clamp(1.0, 100.0) as u8;
                format!("/SEND\t{}\t{}\t{}", pct, source, target)
            }
            ClientMessage::Redir { source, target } => format!("/REDIR\t{}\t{}", source, target),
            ClientMessage::Surrender => "/SURRENDER".to_string(),
            ClientMessage::Tock => "/TOCK".to_string(),
            ClientMessage::Ping(s) => format!("/PING\t{}", s),
            ClientMessage::Message(s) => s.clone(),
        }
    }
}

#[derive(Debug, Error)]
pub enum ParseError {
    #[error("empty message")]
    EmptyMessage,
    #[error("invalid command: {0}")]
    InvalidCommand(String),
    #[error("invalid id for sync: {0}")]
    InvalidSyncId(String),
    #[error("invalid key for /SET: {0}")]
    InvalidSetKey(String),
}

type Chunks<'a> = iter::Peekable<str::SplitTerminator<'a, char>>;

fn take_float(chunks: &mut Chunks) -> f64 {
    chunks.next().and_then(|s| s.parse().ok()).unwrap_or(0.0)
}

fn take_id(chunks: &mut Chunks) -> usize {
    chunks.next().and_then(|s| s.parse().ok()).unwrap_or(0)
}

fn take_str(chunks: &mut Chunks) -> String {
    chunks.next().unwrap_or("").to_string()
}

fn parse_set(chunks: &mut Chunks) -> Result<SetMeta, ParseError> {
    match chunks.next().unwrap_or("") {
        "YOU" => Ok(SetMeta::You(take_id(chunks))),
        "SPEED" => Ok(SetMeta::Speed(take_float(chunks))),
        "STATE" => Ok(SetMeta::State(take_str(chunks))),
        other => Err(ParseError::InvalidSetKey(other.to_string())),
    }
}

fn parse_sync(header: &str, chunks: &mut Chunks) -> Result<Vec<SyncEntity>, ParseError> {
    let mut syncs = Vec::new();

    while let Some(raw_id) = chunks.next() {
        let id = raw_id
            .parse::<usize>()
            .map_err(|_| ParseError::InvalidSyncId(raw_id.to_string()))?;

        let mut sync = SyncEntity {
            id,
            x: None,
            y: None,
            ships: None,
            radius: None,
            owner: None,
            target: None,
        };

        for ch in header.chars() {
            match ch {
                'X' | 'x' => sync.x = Some(take_float(chunks)),
                'Y' | 'y' => sync.y = Some(take_float(chunks)),
                'S' | 's' => sync.ships = Some(take_float(chunks)),
                'R' | 'r' => sync.radius = Some(take_float(chunks)),
                'O' | 'o' => sync.owner = Some(take_id(chunks)),
                'T' | 't' => sync.target = Some(take_id(chunks)),
                _ => return Err(ParseError::InvalidCommand(header.to_string())),
            }
        }

        syncs.push(sync);
    }

    Ok(syncs)
}

pub fn parse_server_message(line: &str) -> Result<ServerMessage, ParseError> {
    let mut chunks = line.split_terminator('\t').peekable();
    let head = chunks.next().ok_or(ParseError::EmptyMessage)?;

    match head {
        "/SET" => Ok(ServerMessage::Set(parse_set(&mut chunks)?)),
        "/RESET" => Ok(ServerMessage::Reset),
        "/USER" => Ok(ServerMessage::User(User {
            id: take_id(&mut chunks),
            name: take_str(&mut chunks),
            color: take_str(&mut chunks),
            team: take_id(&mut chunks),
        })),
        "/PLANET" => Ok(ServerMessage::Planet(Planet {
            id: take_id(&mut chunks),
            owner: take_id(&mut chunks),
            ships: take_float(&mut chunks),
            x: take_float(&mut chunks),
            y: take_float(&mut chunks),
            production: take_float(&mut chunks),
            radius: take_float(&mut chunks),
        })),
        "/FLEET" => Ok(ServerMessage::Fleet(Fleet {
            id: take_id(&mut chunks),
            owner: take_id(&mut chunks),
            ships: take_float(&mut chunks),
            x: take_float(&mut chunks),
            y: take_float(&mut chunks),
            source: take_id(&mut chunks),
            target: take_id(&mut chunks),
            radius: take_float(&mut chunks),
        })),
        "/CANCEL" => Ok(ServerMessage::Cancel(take_id(&mut chunks))),
        "/DESTROY" => Ok(ServerMessage::Destroy(take_id(&mut chunks))),
        "/TICK" => Ok(ServerMessage::Tick(take_float(&mut chunks))),
        "/RESULTS" => Ok(ServerMessage::Results(chunks.map(str::to_string).collect())),
        "/PONG" => Ok(ServerMessage::Pong(take_str(&mut chunks))),
        "/PRINT" => Ok(ServerMessage::Print(take_str(&mut chunks))),
        "/ERROR" => Ok(ServerMessage::Err(take_str(&mut chunks))),
        _ => Ok(ServerMessage::Sync(parse_sync(head, &mut chunks)?)),
    }
}
