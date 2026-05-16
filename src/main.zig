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

    // TODO only do this when an arg is set -- have this here for collecting log samples for now
    // var dir = Io.Dir.cwd();
    // var fname_buf: [128]u8 = undefined;
    // const start_time = Io.Timestamp.now(init.io, Io.Clock.awake);
    // const fname = try std.fmt.bufPrint(&fname_buf, "/home/toast/code/zzbot/data/logs/{d}.log", .{start_time.nanoseconds});
    // var file = try dir.createFile(init.io, fname, .{});
    // defer file.close(init.io);

    // var keylogger_buffer: [4096]u8 = undefined;
    // var keylogger_writer = file.writer(init.io, &keylogger_buffer);

    while (try stdin_reader.interface.takeDelimiter('\n')) |line| {
        try engine.process_command(line);
        try engine.flush_actions(&stdout_writer.interface);
        // try keylogger_writer.interface.print("{s}\n", .{line});
    }
}
