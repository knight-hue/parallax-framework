package dev.parallax.gateway.platform;

import java.util.List;

import dev.parallax.gateway.auth.AuthPrincipal;
import dev.parallax.gateway.auth.JwtService;
import dev.parallax.gateway.common.ApiException;

import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

@RestController
public class PlatformController {
    private final PlatformIdentityService service;
    private final JwtService jwt;

    public PlatformController(PlatformIdentityService service, JwtService jwt) {
        this.service = service; this.jwt = jwt;
    }

    public record UserRequest(@NotBlank @Size(max = 64) String username,
                              @NotBlank @Size(max = 72) String password) {
        @Override public String toString() { return "UserRequest[credentials=redacted]"; }
    }
    public record NameRequest(@NotBlank @Size(max = 120) String name) { }
    public record MemberRequest(@NotBlank @Size(max = 36) String userId, @NotNull ProjectRole role) { }
    public record LoginResponse(String accessToken, String tokenType, PlatformIdentityService.UserView user) {
        @Override public String toString() { return "LoginResponse[token=redacted]"; }
    }

    @PostMapping("/api/v1/platform/users")
    @PreAuthorize("hasRole('ADMIN')")
    public PlatformIdentityService.UserView provision(@AuthenticationPrincipal AuthPrincipal principal,
                                                      @Valid @RequestBody UserRequest request) {
        if (principal == null) throw ApiException.unauthorized("Administrator token required");
        return service.provision(principal.subject(), request.username(), request.password());
    }

    @DeleteMapping("/api/v1/platform/users/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public void disable(@AuthenticationPrincipal AuthPrincipal principal, @PathVariable String id) {
        if (principal == null) throw ApiException.unauthorized("Administrator token required");
        service.disable(principal.subject(), id);
    }

    @PostMapping("/api/v1/auth/login")
    public LoginResponse login(@Valid @RequestBody UserRequest request) {
        if (!jwt.isConfigured()) throw ApiException.serverError("JWT is not configured");
        var user = service.login(request.username(), request.password());
        return new LoginResponse(jwt.issueUserToken(user.id(), user.username()), "Bearer", user);
    }

    @GetMapping("/api/v1/platform/me")
    public PlatformIdentityService.UserView me(@AuthenticationPrincipal AuthPrincipal principal) {
        return service.activeUser(PlatformIdentityService.requireUser(principal));
    }

    @PostMapping("/api/v1/platform/organizations")
    public PlatformIdentityService.Organization createOrganization(@AuthenticationPrincipal AuthPrincipal principal,
                                                                    @Valid @RequestBody NameRequest request) {
        return service.createOrganization(PlatformIdentityService.requireUser(principal), request.name());
    }

    @GetMapping("/api/v1/platform/organizations")
    public List<PlatformIdentityService.Organization> organizations(@AuthenticationPrincipal AuthPrincipal principal) {
        return service.organizations(PlatformIdentityService.requireUser(principal));
    }

    @PostMapping("/api/v1/platform/organizations/{id}/members")
    public void addMember(@AuthenticationPrincipal AuthPrincipal principal, @PathVariable String id,
                          @Valid @RequestBody MemberRequest request) {
        service.addMember(PlatformIdentityService.requireUser(principal), id, request.userId(), request.role());
    }

    @GetMapping("/api/v1/platform/organizations/{id}/members")
    public List<PlatformIdentityService.Member> members(@AuthenticationPrincipal AuthPrincipal principal,
                                                       @PathVariable String id) {
        return service.members(PlatformIdentityService.requireUser(principal), id);
    }

    @DeleteMapping("/api/v1/platform/organizations/{id}/members/{userId}")
    public void removeMember(@AuthenticationPrincipal AuthPrincipal principal, @PathVariable String id,
                             @PathVariable String userId) {
        service.removeMember(PlatformIdentityService.requireUser(principal), id, userId);
    }

    @PostMapping("/api/v1/platform/organizations/{id}/projects")
    public PlatformIdentityService.Project createProject(@AuthenticationPrincipal AuthPrincipal principal,
                                                         @PathVariable String id,
                                                         @Valid @RequestBody NameRequest request) {
        return service.createProject(PlatformIdentityService.requireUser(principal), id, request.name());
    }

    @GetMapping("/api/v1/platform/organizations/{id}/projects")
    public List<PlatformIdentityService.Project> projects(@AuthenticationPrincipal AuthPrincipal principal,
                                                         @PathVariable String id) {
        return service.projects(PlatformIdentityService.requireUser(principal), id);
    }

    @GetMapping("/api/v1/platform/projects/{id}")
    public PlatformIdentityService.Project project(@AuthenticationPrincipal AuthPrincipal principal,
                                                   @PathVariable String id) {
        return service.project(PlatformIdentityService.requireUser(principal), id, ProjectRole.VIEWER);
    }
}
