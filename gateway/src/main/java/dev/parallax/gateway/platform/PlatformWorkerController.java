package dev.parallax.gateway.platform;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import dev.parallax.gateway.auth.AuthPrincipal;
import dev.parallax.gateway.common.ApiException;
import dev.parallax.gateway.config.ParallaxProperties;
import dev.parallax.gateway.task.WorkerProtocol;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

@RestController
public class PlatformWorkerController {
    private final PlatformWorkerCoordinator coordinator;
    private final ParallaxProperties props;
    private final PlatformExecutionSnapshot snapshots;
    private final PlatformArtifactService artifacts;
    public PlatformWorkerController(PlatformWorkerCoordinator coordinator,ParallaxProperties props,PlatformExecutionSnapshot snapshots,PlatformArtifactService artifacts) { this.coordinator=coordinator;this.props=props;this.snapshots=snapshots;this.artifacts=artifacts; }

    @PostMapping("/api/v1/internal/platform/events")
    public PlatformWorkerCoordinator.Acknowledgement receive(@RequestHeader(value="X-Internal-Token",required=false) String token,
            @RequestBody String body) {
        requireInternal(token);
        if(body.length()>8000) throw ApiException.badRequest("Worker event exceeds supported size");
        try { return coordinator.receive(WorkerProtocol.readEvent(body)); }
        catch(java.io.IOException ex) { throw ApiException.badRequest("Invalid worker event contract"); }
    }

    @PostMapping("/api/v1/internal/platform/artifacts")
    public PlatformArtifactService.Artifact artifact(@RequestHeader(value="X-Internal-Token",required=false) String token,
            @RequestBody String body) {
        requireInternal(token);
        if(body.length()>2_100_000) throw ApiException.badRequest("Artifact request exceeds supported size");
        try { return artifacts.put(new com.fasterxml.jackson.databind.ObjectMapper().readValue(body,PlatformArtifactService.Upload.class)); }
        catch(java.io.IOException ex) { throw ApiException.badRequest("Invalid artifact contract"); }
    }

    @PostMapping("/api/v1/internal/platform/execution-snapshot")
    public PlatformExecutionSnapshot.Snapshot snapshot(@RequestHeader(value="X-Internal-Token",required=false) String token,@RequestBody String body) {
        requireInternal(token);
        if(body.length()>8000) throw ApiException.badRequest("Worker task exceeds supported size");
        try { return snapshots.resolve(WorkerProtocol.readTask(body)); }
        catch(java.io.IOException ex) { throw ApiException.badRequest("Invalid worker task contract"); }
    }
    private void requireInternal(String token) {
        String expected=props.getGateway().getInternalToken();
        if(expected==null || expected.isBlank()) throw new ApiException(HttpStatus.SERVICE_UNAVAILABLE,"Worker ingress is not configured");
        if(token==null || !MessageDigest.isEqual(expected.getBytes(StandardCharsets.UTF_8),token.getBytes(StandardCharsets.UTF_8))) throw ApiException.unauthorized("Worker credential required");
    }

    @GetMapping("/api/v1/platform/projects/{projectId}/tasks/{taskId}/events")
    public PlatformWorkerCoordinator.Events events(@AuthenticationPrincipal AuthPrincipal principal,
            @PathVariable String projectId,@PathVariable String taskId,
            @RequestParam(defaultValue="0") long after,@RequestParam(defaultValue="50") int limit) {
        return coordinator.events(PlatformIdentityService.requireUser(principal),projectId,taskId,after,limit);
    }

    @GetMapping("/api/v1/platform/projects/{projectId}/tasks/{taskId}/result")
    public PlatformArtifactService.Artifact result(@AuthenticationPrincipal AuthPrincipal principal,
            @PathVariable String projectId,@PathVariable String taskId) {
        return artifacts.result(PlatformIdentityService.requireUser(principal),projectId,taskId);
    }
}
