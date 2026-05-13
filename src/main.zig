const std = @import("std");
const Io = std.Io;

const proto = @import("proto.zig");

pub fn main(init: std.process.Init) !void {
    const io = init.io;

    var stdin_buffer: [2048]u8 = undefined;
    var stdin_file_reader: Io.File.Reader = .init(.stdin(), io, &stdin_buffer);
    const stdin = &stdin_file_reader.interface;

    var stdout_buffer: [2048]u8 = undefined;
    var stdout_file_writer: Io.File.Writer = .init(.stdout(), io, &stdout_buffer);
    const stdout = &stdout_file_writer.interface;

    while (try stdin.takeDelimiter('\n')) |line| {
        const message = proto.parse_server_message(init.gpa, line) catch |err| {
            std.debug.print("parse error: {t}\n", .{err});
            continue;
        };
        switch (message) {
            .tick => {
                _ = try stdout.write("/TOCK\n");
                try stdout.flush();
            },
            .results => {
                init.gpa.free(message.results);
            },
            .sync => {
                init.gpa.free(message.sync);
            },
            else => {},
        }
    }
}
