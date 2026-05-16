const std = @import("std");

pub const User = struct {
    id: usize,
    team: usize,
    name: []const u8,
    color: []const u8,
};

pub const Planet = struct {
    id: usize,
    owner: usize,
    ships: f64,
    x: f64,
    y: f64,
    production: f64,
    radius: f64,
};

pub const Fleet = struct {
    id: usize,
    owner: usize,
    source: usize,
    target: usize,
    ships: f64,
    x: f64,
    y: f64,
    radius: f64,
};

pub const EntityType = enum { user, planet, fleet };
pub const Entity = union(EntityType) { user: User, planet: Planet, fleet: Fleet };

pub const SetMetaFields = enum { you, speed, state };
pub const SetMetaMessage = union(SetMetaFields) {
    you: usize,
    speed: f64,
    state: []const u8,
};

pub const SyncEntity = struct {
    id: usize,
    x: ?f64 = null,
    y: ?f64 = null,
    ships: ?f64 = null,
    radius: ?f64 = null,
    owner: ?usize = null,
    target: ?usize = null,
};

const ServerCommand = enum { set, reset, user, planet, fleet, cancel, sync, destroy, tick, results, pong, print, err };
pub const ServerMessage = union(ServerCommand) {
    set: SetMetaMessage,
    reset: void,
    user: User,
    planet: Planet,
    fleet: Fleet,
    cancel: usize,
    sync: []SyncEntity,
    destroy: usize,
    tick: f64,
    results: [][]const u8,
    pong: []const u8,
    print: []const u8,
    err: []const u8,

    pub fn deinit(self: ServerMessage, gpa: std.mem.Allocator) void {
        switch (self) {
            .sync => {
                gpa.free(self.sync);
            },
            .results => {
                gpa.free(self.results);
            },
            else => {},
        }
    }
};

const ServerCommandMap = std.StaticStringMap(ServerCommand).initComptime(.{
    .{ "/SET", ServerCommand.set },
    .{ "/RESET", ServerCommand.reset },
    .{ "/USER", ServerCommand.user },
    .{ "/PLANET", ServerCommand.planet },
    .{ "/FLEET", ServerCommand.fleet },
    .{ "/CANCEL", ServerCommand.cancel },
    .{ "/DESTROY", ServerCommand.destroy },
    .{ "/TICK", ServerCommand.tick },
    .{ "/RESULTS", ServerCommand.results },
    .{ "/PONG", ServerCommand.pong },
    .{ "/PRINT", ServerCommand.print },
    .{ "/ERROR", ServerCommand.err },
});

const MessageParseError = error{
    EmptyMessage,
    OutOfMemory,
    InvalidCommand,
    InvalidSyncId,
    InvalidSetKey,
};

fn take_float(it: anytype) f64 {
    const next: []const u8 = it.next() orelse return 0.0;
    return std.fmt.parseFloat(f64, next) catch return 0.0;
}

fn take_id(it: anytype) usize {
    const next: []const u8 = it.next() orelse return 0;
    return std.fmt.parseInt(usize, next, 10) catch return 0;
}

fn take_str(it: anytype) []const u8 {
    return it.next() orelse "";
}

fn take_tail(gpa: std.mem.Allocator, it: anytype) MessageParseError![][]const u8 {
    var tail = try std.ArrayList([]const u8).initCapacity(gpa, 6);
    defer tail.deinit(gpa);

    while (it.next()) |chunk| {
        try tail.append(gpa, chunk);
    }

    return try tail.toOwnedSlice(gpa);
}

fn parse_set_command(it: anytype) MessageParseError!SetMetaMessage {
    const key = take_str(it);
    if (std.mem.eql(u8, key, "YOU")) {
        return SetMetaMessage{ .you = take_id(it) };
    } else if (std.mem.eql(u8, key, "SPEED")) {
        return SetMetaMessage{ .speed = take_float(it) };
    } else if (std.mem.eql(u8, key, "STATE")) {
        return SetMetaMessage{ .state = take_str(it) };
    } else {
        return MessageParseError.InvalidSetKey;
    }
}

fn parse_sync_command(gpa: std.mem.Allocator, header: []const u8, it: anytype) MessageParseError![]SyncEntity {
    var syncs = try std.ArrayList(SyncEntity).initCapacity(gpa, 8);
    defer syncs.deinit(gpa);

    while (it.next()) |id| {
        var sync = SyncEntity{
            .id = std.fmt.parseInt(usize, id, 10) catch return MessageParseError.InvalidSyncId,
        };
        for (header) |f| {
            switch (f) {
                'X', 'x' => {
                    sync.x = take_float(it);
                },
                'Y', 'y' => {
                    sync.y = take_float(it);
                },
                'S', 's' => {
                    sync.ships = take_float(it);
                },
                'R', 'r' => {
                    sync.radius = take_float(it);
                },
                'O', 'o' => {
                    sync.owner = take_id(it);
                },
                'T', 't' => {
                    sync.target = take_id(it);
                },
                else => return MessageParseError.InvalidCommand,
            }
        }
        try syncs.append(gpa, sync);
    }

    return try syncs.toOwnedSlice(gpa);
}

pub fn parse_server_message(gpa: std.mem.Allocator, line: []u8) MessageParseError!ServerMessage {
    var chunks = std.mem.splitScalar(u8, line, '\t');
    const head = chunks.next() orelse return MessageParseError.EmptyMessage;

    if (ServerCommandMap.get(head)) |cmd| {
        return switch (cmd) {
            .set => ServerMessage{ .set = try parse_set_command(&chunks) },
            .reset => ServerMessage{ .reset = {} },
            .user => ServerMessage{ .user = User{
                .id = take_id(&chunks),
                .name = take_str(&chunks),
                .color = take_str(&chunks),
                .team = take_id(&chunks),
            } },
            .planet => ServerMessage{ .planet = Planet{
                .id = take_id(&chunks),
                .owner = take_id(&chunks),
                .ships = take_float(&chunks),
                .x = take_float(&chunks),
                .y = take_float(&chunks),
                .production = take_float(&chunks),
                .radius = take_float(&chunks),
            } },
            .fleet => ServerMessage{ .fleet = Fleet{
                .id = take_id(&chunks),
                .owner = take_id(&chunks),
                .ships = take_float(&chunks),
                .x = take_float(&chunks),
                .y = take_float(&chunks),
                .source = take_id(&chunks),
                .target = take_id(&chunks),
                .radius = take_float(&chunks),
            } },
            .cancel => ServerMessage{ .cancel = take_id(&chunks) },
            .destroy => ServerMessage{ .destroy = take_id(&chunks) },
            .tick => ServerMessage{ .tick = take_float(&chunks) },
            .results => ServerMessage{ .results = try take_tail(gpa, &chunks) },
            .pong => ServerMessage{ .pong = take_str(&chunks) },
            .print => ServerMessage{ .print = take_str(&chunks) },
            .err => ServerMessage{ .err = take_str(&chunks) },
            .sync => unreachable, // handled by tail
        };
    } else {
        // TODO handle sync messages
        return ServerMessage{ .sync = try parse_sync_command(gpa, head, &chunks) };
    }
}

pub const ClientCommand = enum { login, send, redir, surrender, tock, ping, message };
pub const ClientMessage = union(ClientCommand) {
    login: struct {
        name: []const u8,
        token: []const u8,
    },
    send: struct {
        proportion: f64,
        source: usize,
        target: usize,
    },
    redir: struct {
        source: usize,
        target: usize,
    },
    surrender: void,
    tock: void,
    ping: []const u8,
    message: []const u8,

    pub fn format(self: ClientMessage, writer: *std.Io.Writer) !void {
        switch (self) {
            .login => try writer.print("/LOGIN\t{s}\t{s}", .{ self.login.name, self.login.token }),
            .send => {
                const pct: u8 = @round(std.math.clamp(self.send.proportion * 100.0, 1.0, 100.0));
                try writer.print("/SEND\t{d}\t{d}\t{d}", .{ pct, self.send.source, self.send.target });
            },
            .redir => try writer.print("/REDIR\t{d}\t{d}", .{ self.redir.source, self.redir.target }),
            .surrender => try writer.print("/SURRENDER", .{}),
            .tock => try writer.print("/TOCK", .{}),
            .ping => try writer.print("/TOCK\t{s}", .{self.ping}),
            .message => try writer.print("{s}", .{self.message}),
        }
    }
};
