const std = @import("std");

pub fn main() void {
    for (0..5967124) |i| {
        std.debug.print("zig Index: {}\n", .{i});
    }
}
