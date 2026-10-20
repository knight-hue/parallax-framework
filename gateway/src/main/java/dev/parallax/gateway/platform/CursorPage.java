package dev.parallax.gateway.platform;

import java.util.List;
import java.util.function.Function;
import dev.parallax.gateway.common.ApiException;

/** UUID seek pagination: bounded DB reads, without OFFSET scans or mutable name ordering. */
public record CursorPage<T>(List<T> items, String nextCursor) {
    public static void validate(String after, int limit) {
        if (limit < 1 || limit > 100) throw ApiException.badRequest("limit must be 1..100");
        if (after == null || (!after.isEmpty() && !after.matches("[0-9a-f-]{36}"))) {
            throw ApiException.badRequest("Invalid cursor");
        }
    }
    public static <T> CursorPage<T> of(List<T> rows, int limit, Function<T, String> id) {
        boolean more = rows.size() > limit;
        List<T> items = List.copyOf(rows.subList(0, Math.min(rows.size(), limit)));
        return new CursorPage<>(items, more ? id.apply(items.getLast()) : null);
    }
}
