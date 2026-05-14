const std = @import("std");
const Io = std.Io;
const Map = std.array_hash_map.Auto;

const proto = @import("proto.zig");

pub const Engine = struct {
    allocator: std.mem.Allocator,
    pending_actions: std.Deque(proto.ClientMessage),
    users: Map(usize, proto.User),
    planets: Map(usize, proto.Planet),
    fleets: Map(usize, proto.Fleet),
    you: usize,

    pub fn init(alloc: std.mem.Allocator) !Engine {
        return Engine{
            .allocator = alloc,
            .pending_actions = try std.Deque(proto.ClientMessage).initCapacity(alloc, 16),
            .users = try Map(usize, proto.User).init(alloc, &[_]usize{}, &[_]proto.User{}),
            .planets = try Map(usize, proto.Planet).init(alloc, &[_]usize{}, &[_]proto.Planet{}),
            .fleets = try Map(usize, proto.Fleet).init(alloc, &[_]usize{}, &[_]proto.Fleet{}),
            .you = 0,
        };
    }

    pub fn deinit(self: *Engine) void {
        self.pending_actions.deinit(self.allocator);
        self.users.deinit(self.allocator);
        self.planets.deinit(self.allocator);
        self.fleets.deinit(self.allocator);
    }

    fn queue(self: *Engine, action: proto.ClientMessage) void {
        self.pending_actions.pushBack(self.allocator, action) catch |err| {
            std.debug.print("failed to queue {t} action: {t}\n", .{ action, err });
        };
    }

    pub fn process_command(self: *Engine, line: []u8) !void {
        const message = proto.parse_server_message(self.allocator, line) catch |err| {
            std.debug.print("parse error: {t}\n", .{err});
            return;
        };
        defer message.deinit(self.allocator);

        switch (message) {
            .tick => self.queue(proto.ClientMessage{ .tock = {} }),
            else => {},
        }
    }

    pub fn flush_actions(self: *Engine, writer: *Io.Writer) !void {
        var writer_needs_flush: bool = false;

        while (self.pending_actions.popFront()) |action| {
            try proto.serialize_client_message(writer, action);
            writer_needs_flush = true;
        }
        if (writer_needs_flush) {
            try writer.flush();
        }
    }
};
