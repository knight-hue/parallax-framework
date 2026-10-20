package dev.parallax.gateway.platform;

import dev.parallax.gateway.auth.AuthPrincipal;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

@RestController
@RequestMapping("/api/v1/platform/projects/{projectId}")
public class PlatformCatalogController {
    public record RepositoryRequest(@NotBlank @Size(max=120) String name, @NotBlank @Size(max=1024) String cloneUrl) { }
    private final PlatformCatalogService service;
    public PlatformCatalogController(PlatformCatalogService service) { this.service = service; }

    @PostMapping("/repositories")
    public PlatformCatalogService.Repository register(@AuthenticationPrincipal AuthPrincipal principal,
            @PathVariable String projectId, @Valid @RequestBody RepositoryRequest request) {
        return service.register(PlatformIdentityService.requireUser(principal), projectId, request.name(), request.cloneUrl());
    }
    @GetMapping("/repositories")
    public CursorPage<PlatformCatalogService.Repository> repositories(@AuthenticationPrincipal AuthPrincipal principal,
            @PathVariable String projectId, @RequestParam(defaultValue="") String after, @RequestParam(defaultValue="50") int limit) {
        return service.repositories(PlatformIdentityService.requireUser(principal), projectId, after, limit);
    }
    @GetMapping("/repositories/{id}")
    public PlatformCatalogService.Repository repository(@AuthenticationPrincipal AuthPrincipal principal,
            @PathVariable String projectId, @PathVariable String id) {
        return service.repository(PlatformIdentityService.requireUser(principal), projectId, id);
    }
    @PostMapping("/policies")
    public PlatformCatalogService.Policy publish(@AuthenticationPrincipal AuthPrincipal principal,
            @PathVariable String projectId, @RequestBody PlatformCatalogService.PolicyConfig config) {
        return service.publish(PlatformIdentityService.requireUser(principal), projectId, config);
    }
    @GetMapping("/policies")
    public CursorPage<PlatformCatalogService.Policy> policies(@AuthenticationPrincipal AuthPrincipal principal,
            @PathVariable String projectId, @RequestParam(defaultValue="") String after, @RequestParam(defaultValue="50") int limit) {
        return service.policies(PlatformIdentityService.requireUser(principal), projectId, after, limit);
    }
    @GetMapping("/policies/{id}")
    public PlatformCatalogService.Policy policy(@AuthenticationPrincipal AuthPrincipal principal,
            @PathVariable String projectId, @PathVariable String id) {
        return service.policy(PlatformIdentityService.requireUser(principal), projectId, id);
    }
}
