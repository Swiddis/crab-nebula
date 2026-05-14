const std = @import("std");
const math = std.math;
const Io = std.Io;
const Map = std.array_hash_map.Auto;

const proto = @import("proto.zig");

/// Simple prioritizer: score = production / (ships * distance)
fn lazyProductionSorter(context: *const proto.Planet, a: proto.Planet, b: proto.Planet) std.math.Order {
    const dist_a = math.sqrt((a.x - context.x) * (a.x - context.x) + (a.y - context.y) * (a.y - context.y));
    const dist_b = math.sqrt((b.x - context.x) * (b.x - context.x) + (b.y - context.y) * (b.y - context.y));

    return math.order(b.production / (b.ships * dist_b), a.production / (a.ships * dist_a));
}

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

    fn reset(self: *Engine) void {
        // deque doesn't support clear? why?
        while (self.pending_actions.popBack()) |_| {}
        self.users.clearRetainingCapacity();
        self.fleets.clearRetainingCapacity();
        self.planets.clearRetainingCapacity();
    }

    fn queue(self: *Engine, action: proto.ClientMessage) void {
        self.pending_actions.pushBack(self.allocator, action) catch |err| {
            std.debug.print("failed to queue {t} action: {t}\n", .{ action, err });
        };
    }

    fn apply_syncs(self: *Engine, syncs: []proto.SyncEntity) void {
        for (syncs) |sync| {
            if (self.fleets.getPtr(sync.id)) |fleet| {
                fleet.owner = sync.owner orelse fleet.owner;
                fleet.radius = sync.radius orelse fleet.radius;
                fleet.ships = sync.ships orelse fleet.ships;
                fleet.target = sync.target orelse fleet.target;
                fleet.x = sync.x orelse fleet.x;
                fleet.y = sync.y orelse fleet.y;
            } else if (self.planets.getPtr(sync.id)) |planet| {
                planet.owner = sync.owner orelse planet.owner;
                planet.radius = sync.radius orelse planet.radius;
                planet.ships = sync.ships orelse planet.ships;
                planet.x = sync.x orelse planet.x;
                planet.y = sync.y orelse planet.y;
            }
        }
    }

    fn act_as_planet(self: *Engine, planet: *const proto.Planet) void {
        var target_queue = std.PriorityQueue(proto.Planet, *const proto.Planet, lazyProductionSorter).initContext(planet);
        defer target_queue.deinit(self.allocator);

        for (self.planets.values()) |target| {
            if (target.owner == self.you) {
                continue;
            }
            target_queue.push(self.allocator, target) catch return;
        }

        var surplus_ships = planet.ships - 5.0;
        for (self.fleets.values()) |fleet| {
            if (fleet.target != planet.id or fleet.owner == self.you) {
                continue;
            }
            surplus_ships -= 1.1 * fleet.ships;
        }

        while (target_queue.pop()) |target| {
            if (surplus_ships <= 0.0) {
                break;
            }

            const to_send = 1.1 * target.ships;
            if (surplus_ships > to_send) {
                self.queue(proto.ClientMessage{ .send = .{
                    .proportion = to_send / planet.ships,
                    .source = planet.id,
                    .target = target.id,
                } });
                surplus_ships -= to_send;
            }
        }
    }

    fn act(self: *Engine) void {
        for (self.planets.values()) |planet| {
            if (planet.owner == self.you) {
                self.act_as_planet(&planet);
            }
        }
        self.queue(proto.ClientMessage{ .tock = {} });
    }

    pub fn process_command(self: *Engine, line: []u8) !void {
        const message = proto.parse_server_message(self.allocator, line) catch |err| {
            std.debug.print("parse error: {t}\n", .{err});
            return;
        };
        defer message.deinit(self.allocator);

        switch (message) {
            .reset => self.reset(),
            .user => try self.users.put(self.allocator, message.user.id, message.user),
            .fleet => try self.fleets.put(self.allocator, message.fleet.id, message.fleet),
            .planet => try self.planets.put(self.allocator, message.planet.id, message.planet),
            .destroy => _ = self.fleets.swapRemove(message.destroy),
            .sync => self.apply_syncs(message.sync),
            .tick => self.act(),
            .set => switch (message.set) {
                .you => self.you = message.set.you,
                else => {},
            },
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
