package dev.parallax.gateway.platform;

/** Returns only after a durable broker confirmation with no unroutable return. */
@FunctionalInterface
public interface DispatchTransport {
    void publish(PlatformOutboxStore.Claim claim) throws Exception;
}
