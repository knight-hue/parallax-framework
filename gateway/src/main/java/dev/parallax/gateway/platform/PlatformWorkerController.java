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
    public PlatformWorkerController(PlatformWorkerCoordinator coordinator,ParallaxProperties props) { this.coordinator=coordinator;this.props=props; }

    @PostMapping("/api/v1/internal/platform/events")
    public PlatformWorkerCoordinator.Acknowledgement receive(@RequestHeader(value="X-Internal-Token",required=false) String token,
            @RequestBody String body) {
        String expected=props.getGateway().getInternalToken();
        if(expected==null || expected.isBlank()) throw new ApiException(HttpStatus.SERVICE_UNAVAILABLE,"Worker ingress is not configured");
        if(token==null || !MessageDigest.isEqual(expected.getBytes(StandardCharsets.UTF_8),token.getBytes(StandardCharsets.UTF_8))) throw ApiException.unauthorized("Worker credential required");
        if(body.length()>8000) throw ApiException.badRequest("Worker event exceeds supported size");
        try { return coordinator.receive(WorkerProtocol.readEvent(body)); }
        catch(java.io.IOException ex) { throw ApiException.badRequest("Invalid worker event contract"); }
    }

    @GetMapping("/api/v1/platform/projects/{projectId}/tasks/{taskId}/events")
    public PlatformWorkerCoordinator.Events events(@AuthenticationPrincipal AuthPrincipal principal,
            @PathVariable String projectId,@PathVariable String taskId,
            @RequestParam(defaultValue="0") long after,@RequestParam(defaultValue="50") int limit) {
        return coordinator.events(PlatformIdentityService.requireUser(principal),projectId,taskId,after,limit);
    }
}
