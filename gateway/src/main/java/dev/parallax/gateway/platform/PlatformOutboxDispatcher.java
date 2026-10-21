package dev.parallax.gateway.platform;

import dev.parallax.gateway.task.WorkerProtocol;
import dev.parallax.gateway.task.TaskState;
import io.micrometer.core.instrument.MeterRegistry;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/** Broker waits are outside database transactions. A process crash leaves a reclaimable lease. */
public final class PlatformOutboxDispatcher {
    private static final Logger log=LoggerFactory.getLogger(PlatformOutboxDispatcher.class);
    private final PlatformOutboxStore store;
    private final PlatformWorkerCoordinator coordinator;
    private final PlatformTaskService tasks;
    private final DispatchTransport transport;
    private final MeterRegistry metrics;
    public PlatformOutboxDispatcher(PlatformOutboxStore store,PlatformWorkerCoordinator coordinator,
            PlatformTaskService tasks,DispatchTransport transport,MeterRegistry metrics) {
        this.store=store;this.coordinator=coordinator;this.tasks=tasks;this.transport=transport;this.metrics=metrics;
    }
    public boolean publishOne() {
        var next=store.claim();if(next.isEmpty()) return false;
        var claim=next.get();
        try {
            var dispatch=WorkerProtocol.readTask(claim.payload());
            if(!claim.taskId().equals(dispatch.taskId()) || claim.attempt()!=dispatch.attempt()) throw new IllegalStateException("Outbox contract mismatch");
            boolean active;
            if(claim.kind().equals("DISPATCH")) active=coordinator.prepareDispatch(dispatch.taskId(),dispatch.attempt(),dispatch.fencingToken());
            else {
                var current=tasks.current(claim.taskId(),false);
                active=claim.kind().equals("CANCEL") && current.attempt()==dispatch.attempt()
                        && current.fencingToken()==dispatch.fencingToken() && current.state()==TaskState.CANCEL_REQUESTED;
            }
            if(!active) { store.complete(claim,false);metrics.counter("parallax.outbox.superseded").increment();return true; }
            if(!store.owned(claim)) return true;
            transport.publish(claim);
            if(store.complete(claim,true)) metrics.counter("parallax.outbox.published").increment();
        } catch(Exception ex) {
            if(ex instanceof InterruptedException) Thread.currentThread().interrupt();
            store.retry(claim);metrics.counter("parallax.outbox.retry").increment();
            // Do not log broker URI, credentials or external exception bodies.
            log.warn("Outbox publish deferred id={} cause={}",claim.id(),ex.getClass().getSimpleName());
        }
        return true;
    }
}
