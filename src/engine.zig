const std = @import("std");
const math = std.math;
const Io = std.Io;
const Map = std.array_hash_map.Auto;

const proto = @import("proto.zig");
const geom = @import("geom.zig");

/// Simple prioritizer: score = production / (ships * distance)
fn lazyProductionSorter(context: *const proto.Planet, a: proto.Planet, b: proto.Planet) std.math.Order {
    const dist_a = geom.hypot(context, &a);
    const dist_b = geom.hypot(context, &b);
    // Reduce asymptotic effects of near-zero behavior
    const den_a = (2.0 + a.ships) * (2.0 + dist_a);
    const den_b = (2.0 + b.ships) * (2.0 + dist_b);

    return math.order(b.production / den_b, a.production / den_a);
}

pub const Engine = struct {
    allocator: std.mem.Allocator,
    pending_actions: std.ArrayList(proto.ClientMessage),
    users: Map(usize, proto.User),
    planets: Map(usize, proto.Planet),
    fleets: Map(usize, proto.Fleet),
    you: usize,

    pub fn init(alloc: std.mem.Allocator) !Engine {
        return Engine{
            .allocator = alloc,
            .pending_actions = try std.ArrayList(proto.ClientMessage).initCapacity(alloc, 8),
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
        self.pending_actions.clearRetainingCapacity();
        self.users.clearRetainingCapacity();
        self.fleets.clearRetainingCapacity();
        self.planets.clearRetainingCapacity();
    }

    fn queue(self: *Engine, action: proto.ClientMessage) void {
        self.pending_actions.append(self.allocator, action) catch |err| {
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

        // planet tally: find best potential targets relative to current planet
        for (self.planets.values()) |target| {
            if (target.owner == self.you) {
                continue;
            }
            target_queue.push(self.allocator, target) catch return;
        }

        // target-fleet surplus map
        var tfmap = std.AutoHashMap(usize, f64).init(self.allocator);
        defer tfmap.deinit();

        // fleet tally: each fleet is counted as a delta for the ships on their target planet
        for (self.fleets.values()) |fleet| {
            const fships = if (fleet.owner == self.you) fleet.ships else -fleet.ships;
            const tam = fships + (tfmap.get(fleet.target) orelse 0.0);
            tfmap.put(fleet.target, tam) catch return;
        }

        var surplus = planet.ships - 0.05 * planet.production + @min(tfmap.get(planet.id) orelse 0.0, 0.0);

        while (target_queue.pop()) |target| {
            const target_net = target.ships - (tfmap.get(target.id) orelse 0.0) + 0.1 * target.production;
            if (target_net < 1.0) {
                continue;
            }
            if (surplus >= target_net) {
                self.queue(proto.ClientMessage{ .send = .{
                    .proportion = target_net / planet.ships,
                    .source = planet.id,
                    .target = target.id,
                } });
                surplus -= target_net;
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
        for (self.pending_actions.items) |action| {
            // note: we aren't trying to recover in the case where some elements write before failure
            try writer.print("{f}\n", .{action});
        }
        if (self.pending_actions.items.len > 0) {
            self.pending_actions.clearRetainingCapacity();
            try writer.flush();
        }
    }
};
