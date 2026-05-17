const std = @import("std");
const Io = std.Io;

const IO_BUF_SIZE = 2048;

const Engine = @import("engine.zig").Engine;

const CommandLog = struct {
    active: bool = false,
    dest_file: []u8 = undefined,
    buffer: []u8 = undefined,
    file: std.Io.File = undefined,
    writer: std.Io.File.Writer = undefined,

    fn init(alloc: std.mem.Allocator, io: Io, log_dir: [*:0]const u8) !CommandLog {
        var self: CommandLog = .{};
        self.buffer = try alloc.alloc(u8, IO_BUF_SIZE);
        errdefer alloc.free(self.buffer);

        var dir = Io.Dir.cwd();
        const start_time = Io.Timestamp.now(io, Io.Clock.awake);
        self.dest_file = try std.fmt.allocPrint(alloc, "{s}/log_{d}.log", .{ log_dir, start_time });
        errdefer alloc.free(self.dest_file);

        self.file = try dir.createFile(io, self.dest_file, .{});
        self.writer = self.file.writer(io, self.buffer);
        self.active = true;

        return self;
    }

    fn deinit(self: *CommandLog, alloc: std.mem.Allocator, io: Io) void {
        if (!self.active) return;

        self.writer.flush() catch {};

        self.file.close(io);
        alloc.free(self.dest_file);
        alloc.free(self.buffer);
    }

    fn write(self: *CommandLog, log_line: []const u8) !void {
        if (!self.active) return;
        try self.writer.interface.print("{s}\n", .{log_line});
    }
};

pub fn main(init: std.process.Init) !void {
    var engine = try Engine.init(init.gpa);
    defer engine.deinit();

    var stdin_buffer: [IO_BUF_SIZE]u8 = undefined;
    var stdin_reader: Io.File.Reader = .init(.stdin(), init.io, &stdin_buffer);

    var stdout_buffer: [IO_BUF_SIZE]u8 = undefined;
    var stdout_writer: Io.File.Writer = .init(.stdout(), init.io, &stdout_buffer);

    var command_log: CommandLog = .{};
    defer command_log.deinit(init.gpa, init.io);
    if (init.minimal.args.vector.len > 1) {
        command_log = try CommandLog.init(init.gpa, init.io, init.minimal.args.vector[1]);
    }

    while (try stdin_reader.interface.takeDelimiter('\n')) |line| {
        try engine.process_command(line);
        try engine.flush_actions(&stdout_writer.interface);
        try command_log.write(line);
    }
}
