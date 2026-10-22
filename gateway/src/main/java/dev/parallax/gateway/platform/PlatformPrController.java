package dev.parallax.gateway.platform;

import dev.parallax.gateway.auth.AuthPrincipal;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

@RestController
public class PlatformPrController {

    private final PlatformPrService service;

    public PlatformPrController(PlatformPrService service) {
        this.service = service;
    }

    @PostMapping("/api/v1/platform/projects/{projectId}/repositories/{repositoryId}/links")
    public PlatformPrService.Link link(@AuthenticationPrincipal AuthPrincipal principal,
            @PathVariable String projectId, @PathVariable String repositoryId,
            @RequestBody PlatformPrService.LinkRequest request) {
        return service.link(PlatformIdentityService.requireUser(principal), projectId, repositoryId, request);
    }

    @GetMapping("/api/v1/platform/projects/{projectId}/repositories/{repositoryId}/links")
    public CursorPage<PlatformPrService.Link> links(@AuthenticationPrincipal AuthPrincipal principal,
            @PathVariable String projectId, @PathVariable String repositoryId,
            @RequestParam(defaultValue = "") String after,
            @RequestParam(defaultValue = "50") int limit) {
        return service.links(PlatformIdentityService.requireUser(principal), projectId, repositoryId, after, limit);
    }

    /**
     * GitHub pull-request ingress. Authentication is the HMAC signature, not a
     * tenant JWT, so the security chain permits this path and the service verifies
     * the exact raw request body before reading any field.
     */
    @PostMapping("/api/v1/platform/webhooks/github")
    public ResponseEntity<PlatformPrService.DeliveryResult> github(
            @RequestHeader(value = "X-Hub-Signature-256", required = false) String signature,
            @RequestHeader(value = "X-GitHub-Event", required = false) String event,
            @RequestHeader(value = "X-GitHub-Delivery", required = false) String deliveryId,
            @RequestBody String body) {
        var result = service.githubWebhook(signature, event, deliveryId, body);
        return ResponseEntity.status(result.accepted() ? HttpStatus.ACCEPTED : HttpStatus.OK).body(result);
    }

    /** GitLab merge-request ingress: shared token header plus the event UUID as the idempotency key. */
    @PostMapping("/api/v1/platform/webhooks/gitlab")
    public ResponseEntity<PlatformPrService.DeliveryResult> gitlab(
            @RequestHeader(value = "X-Gitlab-Token", required = false) String token,
            @RequestHeader(value = "X-Gitlab-Event", required = false) String event,
            @RequestHeader(value = "X-Gitlab-Event-UUID", required = false) String deliveryId,
            @RequestBody String body) {
        var result = service.gitlabWebhook(token, event, deliveryId, body);
        return ResponseEntity.status(result.accepted() ? HttpStatus.ACCEPTED : HttpStatus.OK).body(result);
    }
}
