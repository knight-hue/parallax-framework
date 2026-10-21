package dev.parallax.gateway.platform;

import io.micrometer.core.instrument.MeterRegistry;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;

public final class PlatformDispatchLoop {
    private static final Logger log=LoggerFactory.getLogger(PlatformDispatchLoop.class);
    private final PlatformOutboxDispatcher dispatcher;
    private final PlatformWorkerCoordinator coordinator;
    private final MeterRegistry metrics;
    public PlatformDispatchLoop(PlatformOutboxDispatcher dispatcher,PlatformWorkerCoordinator coordinator,MeterRegistry metrics) {
        this.dispatcher=dispatcher;this.coordinator=coordinator;this.metrics=metrics;
    }
    @Scheduled(fixedDelayString="${parallax.dispatch.publish-delay-ms:500}",scheduler="platformDispatchScheduler")
    public void publish() {
        for(int i=0;i<10 && !Thread.currentThread().isInterrupted();i++) if(!dispatcher.publishOne()) break;
    }
    @Scheduled(fixedDelayString="${parallax.dispatch.recovery-delay-ms:5000}",scheduler="platformDispatchScheduler")
    public void recover() {
        for(String id:coordinator.recoveryCandidates(100)) {
            try { if(coordinator.recover(id)) metrics.counter("parallax.worker.recovered").increment(); }
            catch(RuntimeException ex) { metrics.counter("parallax.worker.recovery.failure").increment();log.warn("Recovery deferred task={} cause={}",id,ex.getClass().getSimpleName()); }
        }
    }
}
