const std = @import("std");
const Io = std.Io;

const proto = @import("proto.zig");

fn engine_handle_line(gpa: std.mem.Allocator, actions: *std.Deque([]const u8), line: []u8) !void {
    const message = proto.parse_server_message(gpa, line) catch |err| {
        std.debug.print("parse error: {t}\n", .{err});
        return;
    };
    defer message.deinit(gpa);

    switch (message) {
        .tick => try actions.pushBack(gpa, "/TOCK"),
        else => {},
    }
}

fn flush_actions(actions: *std.Deque([]const u8), writer: *Io.Writer) !void {
    var needs_flush: bool = false;

    while (actions.popFront()) |action| {
        try writer.print("{s}\n", .{action});
        needs_flush = true;
    }
    if (needs_flush) {
        try writer.flush();
    }
}

pub fn main(init: std.process.Init) !void {
    var actions = try std.Deque([]const u8).initCapacity(init.gpa, 16);

    var stdin_buffer: [2048]u8 = undefined;
    var stdin_reader: Io.File.Reader = .init(.stdin(), init.io, &stdin_buffer);

    var stdout_buffer: [2048]u8 = undefined;
    var stdout_writer: Io.File.Writer = .init(.stdout(), init.io, &stdout_buffer);

    while (try stdin_reader.interface.takeDelimiter('\n')) |line| {
        try engine_handle_line(init.gpa, &actions, line);
        try flush_actions(&actions, &stdout_writer.interface);
    }
}
