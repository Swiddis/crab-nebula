const std = @import("std");
const Io = std.Io;

const Engine = @import("engine.zig").Engine;

pub fn main(init: std.process.Init) !void {
    var engine = try Engine.init(init.gpa);
    defer engine.deinit();

    var stdin_buffer: [2048]u8 = undefined;
    var stdin_reader: Io.File.Reader = .init(.stdin(), init.io, &stdin_buffer);

    var stdout_buffer: [2048]u8 = undefined;
    var stdout_writer: Io.File.Writer = .init(.stdout(), init.io, &stdout_buffer);

    while (try stdin_reader.interface.takeDelimiter('\n')) |line| {
        try engine.process_command(line);
        try engine.flush_actions(&stdout_writer.interface);
    }
}
