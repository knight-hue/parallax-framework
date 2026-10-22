package dev.parallax.gateway.platform;

import java.nio.charset.StandardCharsets;

import dev.parallax.gateway.auth.AuthPrincipal;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

@RestController
public class PlatformShareController {

    private final PlatformShareService service;

    public PlatformShareController(PlatformShareService service) {
        this.service = service;
    }

    @PostMapping("/api/v1/platform/projects/{projectId}/tasks/{taskId}/shares")
    public ResponseEntity<PlatformShareService.CreatedShare> create(
            @AuthenticationPrincipal AuthPrincipal principal,
            @PathVariable String projectId, @PathVariable String taskId,
            @RequestBody PlatformShareService.CreateRequest request) {
        var created = service.create(PlatformIdentityService.requireUser(principal), projectId, taskId, request);
        return ResponseEntity.status(HttpStatus.CREATED).body(created);
    }

    @GetMapping("/api/v1/platform/projects/{projectId}/tasks/{taskId}/shares")
    public CursorPage<PlatformShareService.ShareView> list(
            @AuthenticationPrincipal AuthPrincipal principal,
            @PathVariable String projectId, @PathVariable String taskId,
            @RequestParam(defaultValue = "") String after,
            @RequestParam(defaultValue = "50") int limit) {
        return service.list(PlatformIdentityService.requireUser(principal), projectId, taskId, after, limit);
    }

    @DeleteMapping("/api/v1/platform/projects/{projectId}/tasks/{taskId}/shares/{shareId}")
    public PlatformShareService.ShareView revoke(
            @AuthenticationPrincipal AuthPrincipal principal,
            @PathVariable String projectId, @PathVariable String taskId, @PathVariable String shareId) {
        return service.revoke(PlatformIdentityService.requireUser(principal), projectId, taskId, shareId);
    }

    /**
     * Anonymous report access. The raw token is the bearer capability; it is
     * deliberately not cached so expiry and revocation take effect immediately.
     */
    @GetMapping("/api/v1/platform/shares/{token}")
    public ResponseEntity<byte[]> access(@PathVariable String token) {
        var result = service.access(token);
        return ResponseEntity.ok()
                .header(HttpHeaders.CACHE_CONTROL, "no-store")
                .header(HttpHeaders.PRAGMA, "no-cache")
                .header("Referrer-Policy", "no-referrer")
                .header("X-Content-Type-Options", "nosniff")
                .header("X-Robots-Tag", "noindex, nofollow")
                .header(HttpHeaders.CONTENT_DISPOSITION, "inline; filename=\"parallax-report.json\"")
                .contentType(MediaType.APPLICATION_JSON)
                .body(result.content().getBytes(StandardCharsets.UTF_8));
    }
}
