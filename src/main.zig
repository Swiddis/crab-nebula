const std = @import("std");
const Io = std.Io;

const proto = @import("proto.zig");
const Action = proto.ClientMessage;

fn engine_handle_line(gpa: std.mem.Allocator, actions: *std.Deque(Action), line: []u8) !void {
    const message = proto.parse_server_message(gpa, line) catch |err| {
        std.debug.print("parse error: {t}\n", .{err});
        return;
    };
    defer message.deinit(gpa);

    switch (message) {
        .tick => try actions.pushBack(gpa, Action{ .tock = {} }),
        else => {},
    }
}

fn flush_actions(actions: *std.Deque(Action), writer: *Io.Writer) !void {
    var needs_flush: bool = false;

    while (actions.popFront()) |action| {
        try proto.serialize_client_message(writer, action);
        needs_flush = true;
    }
    if (needs_flush) {
        try writer.flush();
    }
}

pub fn main(init: std.process.Init) !void {
    var actions = try std.Deque(Action).initCapacity(init.gpa, 16);
    defer actions.deinit(init.gpa);

    var stdin_buffer: [2048]u8 = undefined;
    var stdin_reader: Io.File.Reader = .init(.stdin(), init.io, &stdin_buffer);

    var stdout_buffer: [2048]u8 = undefined;
    var stdout_writer: Io.File.Writer = .init(.stdout(), init.io, &stdout_buffer);

    while (try stdin_reader.interface.takeDelimiter('\n')) |line| {
        try engine_handle_line(init.gpa, &actions, line);
        try flush_actions(&actions, &stdout_writer.interface);
    }
}
